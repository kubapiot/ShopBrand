from types import SimpleNamespace
import streamlit as st
import pandas as pd
from PIL import Image
import base64
import json
import os
import google.generativeai as genai  # Import the Gemini library


# Configure Gemini API key
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])


def convert_file_to_base64_data_url(file_path):
    """
    Converts a local image file to a Base64-encoded data URL.
    (Not directly used with Gemini, but kept for potential utility.)
    """
    with open(file_path, "rb") as file:
        file_content = file.read()
        base64_data = base64.b64encode(file_content).decode("utf-8")

        mime_type = None
        if file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
            mime_type = "image/jpeg"
        elif file_path.endswith(".png"):
            mime_type = "image/png"
        elif file_path.endswith(".gif"):
            mime_type = "image/gif"
        else:
            raise ValueError(f"Unsupported file format for {file_path}")

        return f"data:{mime_type};base64,{base64_data}"



def resize_images_in_folder(folder_path, target_width=1600, output_folder=None):
    """
    Resizes all images in the specified folder to the given width.
    """
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    if output_folder is None:
        output_folder = folder_path
    os.makedirs(output_folder, exist_ok=True)

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            with Image.open(file_path) as img:
                if img.format not in ['JPEG', 'PNG', 'GIF', 'BMP', 'TIFF']:
                    print(f"Skipping non-image file: {filename}")
                    continue

                width_percent = target_width / float(img.size[0])
                target_height = int((float(img.size[1]) * float(width_percent)))
                resized_img = img.resize((target_width, target_height))
                output_path = os.path.join(output_folder, filename)
                resized_img.save(output_path)
                print(f"Resized and saved: {output_path}")

        except Exception as e:
            print(f"Error processing {filename}: {e}")


def get_site_image_paths(siteid, images_folder="static/images"):
    """
    Retrieves file paths of images matching a given siteid.
    """
    if not os.path.exists(images_folder):
        raise FileNotFoundError(f"Images folder not found: {images_folder}")
    all_files = os.listdir(images_folder)
    matching_files = [
        os.path.join(images_folder, f) for f in all_files
        if f.startswith(f"{siteid}_") and os.path.isfile(os.path.join(images_folder, f))
    ]
    return matching_files

def get_site_image_urls(siteid, server_url, images_folder):
    """Retrieves all image URLs for a given siteid."""
    if not os.path.exists(images_folder):
        raise FileNotFoundError(f"Images folder not found: {images_folder}")
    all_files = os.listdir(images_folder)
    matching_files = [f for f in all_files if f.startswith(f"{siteid}_")]
    image_urls = [f"{server_url}/static/images/{file}" for file in matching_files]
    return image_urls


def call_gemini_with_images(images, prompt_text, siteid, output_csv):
    """
    Calls Gemini with images and a prompt, then saves the result to a CSV.

    Args:
        images (list): List of image file paths.
        prompt_text (str): Text prompt.
        siteid (str):  Site ID.
        output_csv (str): Output CSV file path.
    """
    try:
        # Prepare the multi-part input for Gemini
        parts = [prompt_text]
        for image_path in images[:10]:  # Limit to 10 images
             with open(image_path, 'rb') as image_file:
                image_data = image_file.read()
                parts.append({"mime_type": "image/jpeg", "data": image_data}) # or image/png

        # Load the Gemini Pro Vision model
        model = genai.GenerativeModel('gemini-2.0-flash-001')

        # --- Token Counting BEFORE generation ---
        token_count = model.count_tokens(parts)
        input_tokens = token_count.total_tokens
        print(f"Input tokens: {input_tokens}")


        # Generate content with the model
        response = model.generate_content(parts)

        # --- Debugging: Print raw response BEFORE any processing ---
        print(f"Raw response.text (before processing): {response.text}")

        # Parse the JSON-like response (Gemini doesn't have a dedicated JSON mode)
        try:
            #  Clean up response.text to be valid JSON (remove backticks, replace ' with ", fix bool/null)
            json_string = response.text.strip()  # Remove leading/trailing whitespace
            if json_string.startswith("```json"):
                json_string = json_string[7:]
            if json_string.endswith("```"):
                json_string = json_string[:-3]
            json_string = json_string.replace("'", '"').replace('True', 'true').replace('False', 'false').replace('None', 'null')

            print(f"Cleaned JSON string: {json_string}")  # Debug print
            response_json = json.loads(json_string, object_hook=lambda d: SimpleNamespace(**d))


        except json.JSONDecodeError as e:
            print(f"JSONDecodeError: {e}")
            print(f"Raw response text (after stripping): {response.text.strip()}")  # Print stripped text
            return  # Exit if JSON parsing fails

        # --- Placeholder for Output Tokens (Not directly available) ---
        output_tokens = 0  #  Replace with estimation if needed.
        total_tokens = input_tokens + output_tokens

        # Prepare data for CSV
        data = {
            'SiteID': [siteid],
            'hasShop': [getattr(response_json, 'hasShop', None)],  # Use getattr
            'shopBrand': [getattr(response_json, 'shopBrand', None)],
            'accuracy': [getattr(response_json, 'accuracy', None)],
            'Tokens': [total_tokens],
            'usedPhotoDate': [getattr(response_json, 'usedPhotoDate', None)],
            'usedPhotoFileName': [getattr(response_json, 'usedPhotoFileName', None)],
            'isStreetViewPhoto' : [getattr(response_json, 'isStreetViewPhoto', None)],
        }

        df = pd.DataFrame(data)
        file_exists = os.path.isfile(output_csv)
        df.to_csv(output_csv, mode='a', header=not file_exists, index=False)
        print(f"Result saved to {output_csv}")

    except Exception as e:
        print(f"Error: {e}")


def get_unique_siteids(folder_path):
    """
    Extracts unique site IDs from filenames in the given folder.
    """
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    siteids = set()
    for filename in os.listdir(folder_path):
        if "_" in filename:
            siteid = filename.split("_", 1)[0]
            siteids.add(siteid)
    return list(siteids)


# Example usage (Main execution block)
if __name__ == "__main__":
    server_url = "https://f748-91-230-116-132.ngrok-free.app"  # Replace with your server URL
    images_folder = "static/images"
    output_csv = 'gemini_output.csv'
    siteids = get_unique_siteids(images_folder)
    # resize_images_in_folder(images_folder) # Uncomment if you need to resize

    processed_siteids = set()
    if os.path.exists(output_csv):
        existing_data = pd.read_csv(output_csv)
        existing_data["SiteID"] = existing_data["SiteID"].astype(str)
        processed_siteids.update(existing_data['SiteID'].unique())

    prompt_text = """Attached pictures are likely showing a petrol station. Your task is to help with the convenience store.
                            Is there a convenience store at the site?
                            If yes - what is the likely brand of the store (this may be different to the brand of the petrol station itself). 
                            Do not use coffee brands as shop brand - for instance Costa Coffee, Starbucks, etc. are not convenience stores.
                            Costa is not a shop brand . Costa Express is not a shop brand. Costco sites do not have a shop.
                            Some of the common shop brands include Londis, Spar, Nisa, Premier, Budgens, Co-op, Tesco Express, Sainsbury's Local, Morrisons Daily, Asda, ASDA Express, M&S Simply Food, BP Connect, Shell Select, Esso On the Run, Shop'n Drive, etc.
                            Only use the common shop brands if you can clearly identify the sign on the shop or priceboard.
                            Pay attention to dates shown on photos. Use the brand name from recent photos over older photos.
                            Return JSON only with the following fields: hasShop (boolean), shopBrand (string), accuracy (int), usedPhotoFileName, usedPhotoDate (date), isStreetViewPhoto (boolean)
                         """

    for siteid in siteids:
        if siteid in processed_siteids:
            print(f"SiteID {siteid} already processed. Skipping...")
            continue

        images = get_site_image_paths(siteid)
        print(f"Processing SiteID: {siteid}, Images: {images}")  # Debug print
        call_gemini_with_images(images, prompt_text, siteid, output_csv)