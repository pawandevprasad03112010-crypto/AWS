import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import (
    Flask,
    render_template,
    request,
    send_file,
    flash,
)
from werkzeug.utils import secure_filename

from transformer import (
    extract_listings,
    transform_listing,
    migrate_images,
)

app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "local-development-key-change-before-deploying",
)

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "25"))
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

ALLOWED_EXTENSION = ".json"


def get_s3_client():
    """AWS credentials environment variables से पढ़ें।"""

    bucket = os.environ.get("S3_BUCKET", "").strip()
    region = os.environ.get("AWS_REGION", "ap-south-1").strip()

    if not bucket:
        raise RuntimeError("S3_BUCKET environment variable सेट नहीं है।")

    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()

    if not access_key or not secret_key:
        raise RuntimeError(
            "AWS_ACCESS_KEY_ID और AWS_SECRET_ACCESS_KEY सेट नहीं हैं।"
        )

    client = boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    return client, bucket


def read_json_upload(file_storage):
    """अपलोड की गई JSON फाइल पढ़ें और validate करें।"""

    filename = secure_filename(file_storage.filename or "")

    if not filename:
        raise ValueError("फाइल का नाम खाली है।")

    if not filename.lower().endswith(ALLOWED_EXTENSION):
        raise ValueError(
            f"{filename}: केवल .json फाइल स्वीकार की जाती है।"
        )

    raw = file_storage.read()

    if not raw:
        raise ValueError(f"{filename}: फाइल खाली है।")

    try:
        text = raw.decode("utf-8-sig")
        data = json.loads(text)
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"{filename}: फाइल UTF-8 encoding में नहीं है।"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{filename}: JSON में त्रुटि है, लाइन {exc.lineno}।"
        ) from exc

    return filename, data


def read_schema_upload(file_storage):
    """वैकल्पिक schema configuration पढ़ें।"""

    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)

    if not filename.lower().endswith(".json"):
        raise ValueError("Schema configuration .json फाइल होनी चाहिए।")

    try:
        config = json.load(
            io.TextIOWrapper(
                file_storage.stream,
                encoding="utf-8-sig",
            )
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Schema configuration का JSON अमान्य है।") from exc

    if not isinstance(config, dict):
        raise ValueError("Schema configuration JSON object होना चाहिए।")

    if not isinstance(config.get("template"), dict):
        raise ValueError(
            "Schema configuration में 'template' JSON object होना चाहिए।"
        )

    if not isinstance(config.get("field_map", {}), dict):
        raise ValueError("'field_map' JSON object होना चाहिए।")

    return config


def safe_output_name(value):
    """ZIP के अंदर इस्तेमाल के लिए सुरक्षित नाम बनाएँ।"""

    value = secure_filename(value or "")
    value = re.sub(r"\.json$", "", value, flags=re.IGNORECASE)

    return value or "listings"


def make_s3_prefix():
    prefix = os.environ.get(
        "S3_PREFIX",
        "migrated-listings",
    ).strip().strip("/")

    return prefix or "migrated-listings"


def create_output_zip(
    uploaded_files,
    schema_config=None,
    should_migrate_images=False,
):
    """हर listing की JSON फाइल बनाकर ZIP तैयार करें।"""

    output_buffer = io.BytesIO()

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_files": [],
        "total_listings": 0,
        "successful_image_migrations": 0,
        "warnings": [],
    }

    s3_client = None
    bucket = None

    if should_migrate_images:
        s3_client, bucket = get_s3_client()

    prefix = make_s3_prefix()
    used_names = set()

    with zipfile.ZipFile(
        output_buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as output_zip:

        for uploaded_file in uploaded_files:
            filename, source_data = read_json_upload(uploaded_file)
            listings = extract_listings(source_data)

            folder_name = safe_output_name(filename)

            report["input_files"].append({
                "filename": filename,
                "listing_count": len(listings),
            })

            for index, source_listing in enumerate(listings, start=1):
                output_listing = transform_listing(
                    source_listing,
                    schema_config,
                )

                if should_migrate_images:
                    before_warnings = len(report["warnings"])

                    output_listing, image_warnings = migrate_images(
                        listing=output_listing,
                        s3_client=s3_client,
                        bucket=bucket,
                        prefix=prefix,
                        public_base_url=os.environ.get(
                            "S3_PUBLIC_BASE_URL",
                            "",
                        ).strip().rstrip("/"),
                    )

                    report["warnings"].extend(image_warnings)

                    if len(report["warnings"]) == before_warnings:
                        report["successful_image_migrations"] += 1

                output_name = (
                    f"{folder_name}/listing_{index:04d}.json"
                )

                if output_name in used_names:
                    output_name = (
                        f"{folder_name}_{len(used_names)}/"
                        f"listing_{index:04d}.json"
                    )

                used_names.add(output_name)

                output_zip.writestr(
                    output_name,
                    json.dumps(
                        output_listing,
                        ensure_ascii=False,
                        indent=2,
                    ),
                )

                report["total_listings"] += 1

        output_zip.writestr(
            "processing_report.json",
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            ),
        )

    output_buffer.seek(0)

    return output_buffer, report


@app.route("/", methods=["GET"])
def index():
    """मुख्य अपलोड पेज दिखाएँ।"""

    s3_ready = all([
        os.environ.get("AWS_ACCESS_KEY_ID"),
        os.environ.get("AWS_SECRET_ACCESS_KEY"),
        os.environ.get("S3_BUCKET"),
    ])

    return render_template(
        "index.html",
        s3_ready=s3_ready,
    )


@app.route("/process", methods=["POST"])
def process_files():
    """JSON फाइलों को process करके ZIP डाउनलोड कराएँ।"""

    uploaded_files = [
        item
        for item in request.files.getlist("source_json")
        if item and item.filename
    ]

    if not uploaded_files:
        flash("पहले कम-से-कम एक JSON फाइल चुनें।", "error")
        return render_template(
            "index.html",
            s3_ready=False,
        ), 400

    schema_config = None

    try:
        schema_config = read_schema_upload(
            request.files.get("schema_json")
        )

        should_migrate_images = (
            request.form.get("migrate_to_s3") == "yes"
        )

        zip_buffer, report = create_output_zip(
            uploaded_files=uploaded_files,
            schema_config=schema_config,
            should_migrate_images=should_migrate_images,
        )

        filename = (
            "listing_migration_"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            + ".zip"
        )

        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=filename,
        )

    except (
        ValueError,
        RuntimeError,
        BotoCoreError,
        ClientError,
    ) as exc:
        app.logger.exception("Listing processing failed")

        flash(f"प्रोसेसिंग नहीं हो सकी: {exc}", "error")

        s3_ready = all([
            os.environ.get("AWS_ACCESS_KEY_ID"),
            os.environ.get("AWS_SECRET_ACCESS_KEY"),
            os.environ.get("S3_BUCKET"),
        ])

        return render_template(
            "index.html",
            s3_ready=s3_ready,
        ), 400

    except Exception:
        app.logger.exception("Unexpected processing error")

        flash(
            "एक अप्रत्याशित त्रुटि हुई। Render के लॉग जाँचें।",
            "error",
        )

        s3_ready = all([
            os.environ.get("AWS_ACCESS_KEY_ID"),
            os.environ.get("AWS_SECRET_ACCESS_KEY"),
            os.environ.get("S3_BUCKET"),
        ])

        return render_template(
            "index.html",
            s3_ready=s3_ready,
        ), 500


@app.errorhandler(413)
def upload_too_large(error):
    """बहुत बड़ी अपलोड फाइल के लिए संदेश।"""

    return (
        f"अपलोड का कुल आकार {MAX_UPLOAD_MB} MB से अधिक है।",
        413,
    )


@app.route("/health", methods=["GET"])
def health():
    """Render health check endpoint."""

    return {
        "status": "ok",
        "service": "listing-json-migrator",
    }, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
      )
def extract_listings(data):
    """JSON डेटा से listings की सूची निकालें।"""

    if isinstance(data, list):
        if not all(isinstance(item, dict) for item in data):
            raise ValueError("हर listing एक JSON object होनी चाहिए।")
        return data

    if isinstance(data, dict):
        for key in (
            "listings",
            "items",
            "data",
            "results",
            "properties",
            "records",
        ):
            value = data.get(key)

            if isinstance(value, list):
                if not all(isinstance(item, dict) for item in value):
                    raise ValueError(
                        f"'{key}' में हर listing JSON object होनी चाहिए।"
                    )
                return value

        return [data]

    raise ValueError("JSON का प्रारूप सही नहीं है।")


def get_path(data, path):
    """Nested JSON से dotted path का value निकालें।"""

    current = data

    for part in str(path).split("."):
        if isinstance(current, dict):
            current = current.get(part)

        elif (
            isinstance(current, list)
            and part.isdigit()
            and int(part) < len(current)
        ):
            current = current[int(part)]

        else:
            return None

    return current


def set_path(data, path, value):
    """Nested JSON में दिए गए path पर value सेट करें।"""

    parts = str(path).split(".")
    current = data

    for part in parts[:-1]:
        if (
            part not in current
            or not isinstance(current[part], dict)
        ):
            current[part] = {}

        current = current[part]

    current[parts[-1]] = value


def collect_text(value, output):
    """JSON में मौजूद text को amenity matching के लिए इकट्ठा करें।"""

    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                collect_text(item, output)

            elif isinstance(item, (str, int, float)):
                if not re.search(
                    r"url|image|photo|phone|mobile|email|contact",
                    str(key),
                    re.IGNORECASE,
                ):
                    output.append(str(item))

    elif isinstance(value, list):
        for item in value:
            collect_text(item, output)

    elif isinstance(value, str):
        output.append(value)


def find_amenities(source):
    """Keyword matching से amenities पहचानें।"""

    text_parts = []
    collect_text(source, text_parts)

    searchable_text = " ".join(text_parts).lower()
    found = []

    for amenity, patterns in AMENITY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, searchable_text, re.IGNORECASE):
                found.append(amenity)
                break

    # Source JSON में पहले से मौजूद amenities भी शामिल करें।
    for key in (
        "amenities",
        "features",
        "facilities",
        "property_amenities",
    ):
        existing = source.get(key)

        if isinstance(existing, list):
            for item in existing:
                if isinstance(item, str) and item.strip():
                    found.append(item.strip())

                elif isinstance(item, dict):
                    name = (
                        item.get("name")
                        or item.get("title")
                        or item.get("label")
                    )

                    if name:
                        found.append(str(name).strip())

        elif isinstance(existing, str):
            found.extend(
                item.strip()
                for item in re.split(r"[,;|]", existing)
                if item.strip()
            )

    # Duplicate amenities हटाएँ।
    unique = []
    seen = set()

    for item in found:
        normalized = item.casefold()

        if normalized not in seen:
            seen.add(normalized)
            unique.append(item)

    return unique


def transform_listing(source, schema_config=None):
    """Source listing को target JSON में बदलें।"""

    if not isinstance(source, dict):
        raise ValueError("Listing JSON object होना चाहिए।")

    amenities = find_amenities(source)

    if not schema_config:
        output = dict(source)
        output["amenities"] = amenities
        return output

    template = schema_config.get("template", {})

    if not isinstance(template, dict):
        raise ValueError("Schema template JSON object होना चाहिए।")

    output = json.loads(
        json.dumps(template, ensure_ascii=False)
    )

    field_map = schema_config.get("field_map", {})

    if not isinstance(field_map, dict):
        raise ValueError("field_map JSON object होना चाहिए।")

    for target_path, source_path in field_map.items():
        value = get_path(source, source_path)

        if value is not None:
            set_path(output, target_path, value)

    amenities_target = schema_config.get(
        "amenities_target",
        "amenities",
    )

    set_path(output, amenities_target, amenities)

    return output
def migrate_images(
    listing,
    s3_client,
    bucket,
    prefix="migrated-listings",
    public_base_url="",
):
    """Nested JSON में image URLs खोजकर S3 पर अपलोड करें।"""

    import hashlib
    import mimetypes
    from urllib.parse import urlparse, unquote

    import requests

    warnings = []
    seen_urls = {}
    prefix = prefix.strip("/")

    def upload_image(url):
        if url in seen_urls:
            return seen_urls[url]

        try:
            parsed = urlparse(url)

            if parsed.scheme not in ("http", "https"):
                warnings.append(f"Unsupported image URL: {url}")
                return url

            response = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": "ListingImageMigrator/1.0"},
                stream=True,
            )
            response.raise_for_status()

            content_type = response.headers.get(
                "Content-Type", ""
            ).split(";")[0].strip().lower()

            if not content_type.startswith("image/"):
                warnings.append(f"URL did not return an image: {url}")
                response.close()
                return url

            image_data = response.content
            response.close()

            if not image_data:
                warnings.append(f"Empty image response: {url}")
                return url

            digest = hashlib.sha256(
                image_data
            ).hexdigest()

            extension = mimetypes.guess_extension(
                content_type
            ) or ".img"

            key = f"{prefix}/{digest}{extension}"

            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=image_data,
                ContentType=content_type,
            )

            if public_base_url:
                new_url = (
                    f"{public_base_url.rstrip('/')}/{key}"
                )
            else:
                region = s3_client.meta.region_name or "ap-south-1"
                new_url = (
                    f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
                )

            seen_urls[url] = new_url
            return new_url

        except Exception as exc:
            warnings.append(
                f"Image migration failed for {url}: {exc}"
            )
            return url

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str) and item.startswith(
                    ("http://", "https://")
                ):
                    key_lower = key.lower()

                    if any(
                        word in key_lower
                        for word in (
                            "image",
                            "photo",
                            "picture",
                            "thumbnail",
                            "gallery",
                            "media",
                        )
                    ):
                        value[key] = upload_image(item)

                elif isinstance(item, (dict, list)):
                    walk(item)

        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str) and item.startswith(
                    ("http://", "https://")
                ):
                    value[index] = upload_image(item)

                elif isinstance(item, (dict, list)):
                    walk(item)

    walk(listing)

    return listing, warnings
