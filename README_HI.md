
# Real Estate Listing JSON Migrator

यह प्रोजेक्ट रियल एस्टेट लिस्टिंग JSON फाइलों को प्रोसेस करने के लिए बनाया गया है।

## मुख्य सुविधाएँ

- एक साथ कई JSON फाइलें अपलोड करना।
- JSON डेटा से अलग-अलग लिस्टिंग निकालना।
- `schema_template.json` के आधार पर डेटा बदलने की सुविधा।
- कीवर्ड के माध्यम से amenities पहचानना।
- वैकल्पिक रूप से इमेज को AWS S3 पर माइग्रेट करना।
- प्रोसेस की गई फाइलों को ZIP में डाउनलोड करना।
- प्रोसेसिंग रिपोर्ट और चेतावनियाँ दिखाना।

## आवश्यक फाइलें

- `app.py` — Flask वेब ऐप।
- `transformer.py` — JSON प्रोसेसिंग और इमेज माइग्रेशन।
- `requirements.txt` — Python dependencies।
- `render.yaml` — Render deployment configuration।
- `schema_template.json` — आउटपुट schema की configuration।
- `AMENITIES_README.md` — amenities पहचानने की जानकारी।
- `README_HI.md` — हिंदी प्रोजेक्ट गाइड।

## GitHub पर अपलोड करना

इस repository की सभी आवश्यक फाइलें और `templates/index.html` फाइल अपलोड करें।

## Render पर Deploy करना

1. Render अकाउंट खोलें।
2. GitHub repository को Render से कनेक्ट करें।
3. उपलब्ध `render.yaml` configuration के अनुसार Web Service बनाएँ।
4. AWS S3 इस्तेमाल करना हो, तो Render के Environment Variables में AWS credentials सेट करें।
5. Deploy पूरा होने पर ऐप का URL खोलें।

## AWS सुरक्षा

- AWS Secret Access Key को GitHub पर कभी अपलोड न करें।
- पहले उजागर हुई AWS keys को revoke करके नई keys बनाएँ।
- AWS credentials केवल Render Environment Variables में रखें।
- AWS IAM permissions को आवश्यक S3 bucket और operations तक सीमित रखें।

## महत्वपूर्ण बातें

- सही आउटपुट बनाने के लिए वास्तविक target JSON schema की configuration आवश्यक है।
- इमेज माइग्रेशन के लिए AWS S3 permissions सही होनी चाहिए।
- S3 पर अपलोड की गई इमेज सार्वजनिक रूप से उपलब्ध होंगी या नहीं, यह bucket permissions और URL configuration पर निर्भर करता है।
- अंतिम JSON और इमेज URLs को इस्तेमाल करने से पहले जाँचें।
- 
