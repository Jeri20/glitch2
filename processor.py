from extractor import extract_entities

def process_message(sender, name, text, timestamp):

    extracted = extract_entities(text)

    structured_data = {
        "user": {
            "name": name,
            "phone": sender
        },
        "message": text,
        "timestamp": timestamp,
        "extracted_data": extracted
    }

    print("\nStructured JSON Output:")
    print(structured_data)

    return structured_data