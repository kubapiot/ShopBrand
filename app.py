from types import SimpleNamespace
import streamlit as st
import pandas as pd

# Load the CSV data
from openai import OpenAI
from PIL import Image
import base64
import json
import os
import backoff 


# Set your OpenAI API key
client = OpenAI(
  api_key=st.secrets["OPENAI_KEY"]
)

def convert_file_to_base64_data_url(file_path):
    """
    Converts a local image file to a Base64-encoded data URL.

    Args:
        file_path (str): Path to the image file.

    Returns:
        str: Base64-encoded data URL.
    """
    with open(file_path, "rb") as file:
        # Read file content and encode in Base64
        file_content = file.read()
        base64_data = base64.b64encode(file_content).decode("utf-8")
        
        # Get MIME type based on file extension
        mime_type = None
        if file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
            mime_type = "image/jpeg"
        elif file_path.endswith(".png"):
            mime_type = "image/png"
        elif file_path.endswith(".gif"):
            mime_type = "image/gif"
        else:
            raise ValueError(f"Unsupported file format for {file_path}")
        
        # Construct and return the data URL
        return f"data:{mime_type};base64,{base64_data}"



def resize_images_in_folder(folder_path, target_width=1600, output_folder=None):
    """
    Resizes all images in the specified folder to the given width while maintaining aspect ratio.

    Args:
        folder_path (str): Path to the folder containing the images.
        target_width (int): Target width in pixels (default is 1600).
        output_folder (str): Optional. Path to save resized images. Defaults to the same folder.

    Returns:
        None
    """
    # Ensure the folder exists
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    # Use the same folder for output if no output folder is specified
    if output_folder is None:
        output_folder = folder_path

    # Create the output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # Iterate over all files in the folder
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        try:
            # Open the image file
            with Image.open(file_path) as img:
                # Check if the file is an image
                if img.format not in ['JPEG', 'PNG', 'GIF', 'BMP', 'TIFF']:
                    print(f"Skipping non-image file: {filename}")
                    continue

                # Calculate the new height to maintain aspect ratio
                width_percent = target_width / float(img.size[0])
                target_height = int((float(img.size[1]) * float(width_percent)))

                # Resize the image
                resized_img = img.resize((target_width, target_height))

                # Save the resized image to the output folder
                output_path = os.path.join(output_folder, filename)
                resized_img.save(output_path)
                print(f"Resized and saved: {output_path}")

        except Exception as e:
            print(f"Error processing {filename}: {e}")


def get_site_image_paths(siteid, images_folder="static/images"):
    """
    Retrieves the file paths of all images matching a given siteid.

    Args:
        siteid (str): The site ID to filter images by.
        images_folder (str): Path to the folder containing the images.

    Returns:
        list: A list of file paths for the images that match the siteid.
    """
    # Ensure the folder exists
    if not os.path.exists(images_folder):
        raise FileNotFoundError(f"Images folder not found: {images_folder}")
    
    # List all files in the folder
    all_files = os.listdir(images_folder)

    # Filter files that start with the siteid and are actual files
    matching_files = [
        os.path.join(images_folder, f) for f in all_files 
        if f.startswith(f"{siteid}_") and os.path.isfile(os.path.join(images_folder, f))
    ]

    return matching_files

def get_site_image_urls(siteid, server_url, images_folder):
    """
    Retrieves all image URLs for a given siteid.

    Args:
        siteid (str): The site ID to filter images by.
        server_url (str): The base server URL to append before the image path.
        images_folder (str): Path to the folder containing the images.

    Returns:
        list: A list of URLs for the images that match the siteid.
    """
    # Ensure the folder exists
    if not os.path.exists(images_folder):
        raise FileNotFoundError(f"Images folder not found: {images_folder}")
    
    # List all files in the folder
    all_files = os.listdir(images_folder)

    # Filter files that start with the siteid and follow the expected naming convention
    matching_files = [
        f for f in all_files if f.startswith(f"{siteid}_")
    ]

    # Construct full URLs for the matching files
    image_urls = [f"{server_url}/static/images/{file}" for file in matching_files]

    return image_urls


def call_chatgpt_with_images(images, prompt_text,siteid, output_csv):
    """
    Calls ChatGPT with a dynamic number of image links and a prompt, then saves the result to a CSV file.

    Args:
        image_links (list): List of image URLs to include in the prompt.
        prompt_text (str): Text to include in the prompt.
        output_csv (str): Path to the output CSV file. Defaults to 'output.csv'.

    Returns:
        None
    """
    try:
        
        image_entries = []
        for image in images[:10]:
            image_entry = {
                "type": "image_url",
                "image_url": {
                    "url": convert_file_to_base64_data_url(image),
                }
            }
            image_entries.append(image_entry)

        # Call ChatGPT
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        *image_entries
                    ],
                }
            ],
            max_tokens=300,
            response_format={ "type": "json_object" },
        )
        # Extract the assistant's response
        chatgpt_response = json.loads(response.choices[0].message.content, object_hook=lambda d: SimpleNamespace(**d))
        
        # Prepare data for the CSV
        data = {
            'SiteID': [siteid],
            'hasShop':chatgpt_response.hasShop,
            'shopBrand':chatgpt_response.shopBrand,
            'accuracy':chatgpt_response.accuracy,
            'Tokens':response.usage.total_tokens

        }

        # Save to CSV 
        df = pd.DataFrame(data)
         # Save to CSV (append mode)
        file_exists = os.path.isfile(output_csv)
        df.to_csv(output_csv, mode='a', header=not file_exists, index=False)

        print(f"Result saved to {output_csv}")

    except Exception as e:
        print(f"Error: {e}")


def get_unique_siteids(folder_path):
    """
    Extracts and returns a list of unique site IDs from filenames in the given folder.
    The site ID is the part of the filename before the first underscore.

    Args:
        folder_path (str): Path to the folder containing the files.

    Returns:
        list: A list of unique site IDs.
    """
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    # Extract site IDs from filenames
    siteids = set()
    for filename in os.listdir(folder_path):
        if "_" in filename:  # Check if the filename contains an underscore
            siteid = filename.split("_", 1)[0]  # Extract the part before the first underscore
            siteids.add(siteid)

    return list(siteids)

# Example usage
if __name__ == "__main__":

    
    
    server_url = "https://f748-91-230-116-132.ngrok-free.app"
    images_folder = "static/images"
    output_csv = 'chatgpt_output.csv'
    siteids = get_unique_siteids(images_folder)
    #resize_images_in_folder(images_folder)

    
    # Load already processed site IDs from the CSV
    processed_siteids = set()
    if os.path.exists(output_csv):
        existing_data = pd.read_csv(output_csv)
        existing_data["SiteID"] = existing_data["SiteID"].astype(str)
        processed_siteids.update(existing_data['SiteID'].unique())

    # Prompt text
    prompt_text = """       Attached pictures are likely showing a petrol station. Your task is to help with the convenience store.
                            Is there a convenience store at the site? 
                            If yes - what is the likely brand of the store (this may be different to the brand of the petrol station itself).
                            Pay attention to dates shown on photos. Use the brand name from recent photos over older photos.
                            Return JSON only with the following fields: hasShop (boolean), shopBrand (string), accuracy (int),usedPhotoFileName, usedPhotoDate (date), isStreetViewPhoto (boolean)
                         """
    try:
        #image_urls = get_site_image_urls(siteid, server_url, images_folder)
        
        for siteid in siteids:
            if siteid in processed_siteids:
                print(f"SiteID {siteid} has already been processed. Skipping...")
                continue
            images = get_site_image_paths(siteid)
            for image in images:
                print(images)
            # Call the ChatGPT function
            call_chatgpt_with_images(images, prompt_text,siteid, output_csv=output_csv)
    except FileNotFoundError as e:
        print(e)

  

    
