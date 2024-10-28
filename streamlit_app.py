import streamlit as st
import cv2
import numpy as np
import pandas as pd
import tempfile
import os
import logging
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from io import BytesIO

# Configure logging
logging.basicConfig(
    filename='app.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Constants
GDRIVE_FOLDER_ID = 'YOUR_GOOGLE_DRIVE_FOLDER_ID'  # Replace with your Google Drive folder ID
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png']

# Initialize Google Drive authentication
def authenticate_drive():
    """
    Authenticate and create a PyDrive GoogleDrive instance.
    
    Returns:
        GoogleDrive: Authenticated GoogleDrive instance.
    """
    try:
        gauth = GoogleAuth()
        gauth.LoadCredentialsFile("credentials.json")
        if gauth.credentials is None:
            gauth.LocalWebserverAuth()  # Creates local webserver and auto handles authentication.
        elif gauth.access_token_expired:
            gauth.Refresh()
        else:
            gauth.Authorize()
        gauth.SaveCredentialsFile("credentials.json")
        drive = GoogleDrive(gauth)
        logging.info("Successfully authenticated with Google Drive.")
        return drive
    except Exception as e:
        logging.error(f"Google Drive authentication failed: {e}")
        st.error("Failed to authenticate with Google Drive. Please check the logs.")
        return None

# Function to upload file to Google Drive
def upload_to_drive(drive, file_obj, folder_id=None):
    """
    Upload a file to Google Drive.
    
    Args:
        drive (GoogleDrive): Authenticated GoogleDrive instance.
        file_obj (BytesIO): File object to upload.
        folder_id (str, optional): ID of the folder to upload the file to.
    
    Returns:
        str: ID of the uploaded file.
    """
    try:
        file_name = file_obj.name
        file = drive.CreateFile({'title': file_name, 'parents': [{'id': folder_id}]}) if folder_id else drive.CreateFile({'title': file_name})
        file.SetContentFile(file_obj)
        file.Upload()
        logging.info(f"Uploaded {file_name} to Google Drive with ID: {file['id']}")
        return file['id']
    except Exception as e:
        logging.error(f"Failed to upload {file_obj.name} to Google Drive: {e}")
        st.error(f"Failed to upload {file_obj.name} to Google Drive.")
        return None

# Function to list images in a Google Drive folder
def list_drive_images(drive, folder_id):
    """
    List image files in a specific Google Drive folder.
    
    Args:
        drive (GoogleDrive): Authenticated GoogleDrive instance.
        folder_id (str): ID of the Google Drive folder.
    
    Returns:
        list: List of file dictionaries.
    """
    try:
        query = f"'{folder_id}' in parents and trashed=false and (mimeType='image/jpeg' or mimeType='image/png')"
        file_list = drive.ListFile({'q': query}).GetList()
        logging.info(f"Retrieved {len(file_list)} images from Google Drive folder ID: {folder_id}")
        return file_list
    except Exception as e:
        logging.error(f"Failed to list images from Google Drive folder ID {folder_id}: {e}")
        st.error("Failed to retrieve images from Google Drive.")
        return []

# Function to download an image from Google Drive
def download_image(drive, file_id):
    """
    Download an image file from Google Drive.
    
    Args:
        drive (GoogleDrive): Authenticated GoogleDrive instance.
        file_id (str): ID of the file to download.
    
    Returns:
        np.ndarray: Image in OpenCV format.
    """
    try:
        file = drive.CreateFile({'id': file_id})
        file.GetContentFile('temp_image')
        image = cv2.imread('temp_image')
        os.remove('temp_image')
        if image is None:
            raise ValueError("Downloaded image is None.")
        logging.info(f"Downloaded image ID: {file_id}")
        return image
    except Exception as e:
        logging.error(f"Failed to download image ID {file_id}: {e}")
        st.error("Failed to download an image from Google Drive.")
        return None

# Streamlit application
def main():
    # Authenticate with Google Drive
    drive = authenticate_drive()
    if drive is None:
        st.stop()

    st.set_page_config(page_title="Image Annotation Tool", layout="wide")
    st.title("📸 Image Annotation Tool")
    st.write("Upload images to annotate and save annotations to Google Drive.")

    # Sidebar for displaying images and uploading new ones
    st.sidebar.header("📂 Google Drive Images")
    
    # Display images from Google Drive in the sidebar
    drive_images = list_drive_images(drive, GDRIVE_FOLDER_ID)
    
    if drive_images:
        st.sidebar.write(f"**{len(drive_images)} Images Found**")
        for img_file in drive_images:
            try:
                # Generate a link to the image
                image_url = f"https://drive.google.com/uc?id={img_file['id']}"
                st.sidebar.image(image_url, caption=img_file['title'], use_column_width=True, width=100)
            except Exception as e:
                logging.error(f"Failed to display image {img_file['title']} in sidebar: {e}")
                st.sidebar.error(f"Failed to display image {img_file['title']}.")
    else:
        st.sidebar.write("No images found in the specified folder.")

    st.sidebar.header("📤 Upload New Images")
    uploaded_files = st.sidebar.file_uploader(
        "Upload Images", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True
    )

    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()
            if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
                st.sidebar.warning(f"File {uploaded_file.name} has an unsupported extension.")
                logging.warning(f"Attempted to upload unsupported file type: {uploaded_file.name}")
                continue
            # Save uploaded file to a temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
                tmp_file.write(uploaded_file.getbuffer())
                tmp_file_path = tmp_file.name
            # Upload to Google Drive
            file_id = upload_to_drive(drive, tmp_file_path, GDRIVE_FOLDER_ID)
            if file_id:
                st.sidebar.success(f"Uploaded {uploaded_file.name} successfully.")
            else:
                st.sidebar.error(f"Failed to upload {uploaded_file.name}.")
            # Remove the temporary file
            os.remove(tmp_file_path)

    st.sidebar.markdown("---")
    st.sidebar.write("Developed by [Your Name](https://yourwebsite.com)")

    # Main Area for Image Annotation
    st.header("🖼️ Annotate Images")
    
    # Initialize session state for annotations
    if 'annotations' not in st.session_state:
        st.session_state['annotations'] = []

    # Fetch and display images for annotation
    if drive_images:
        # Create a dropdown to select an image for annotation
        image_options = {img['title']: img['id'] for img in drive_images}
        selected_image_title = st.selectbox("Select an image to annotate", list(image_options.keys()))
        selected_image_id = image_options[selected_image_title]
        image = download_image(drive, selected_image_id)
        
        if image is not None:
            # Display the image
            st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), caption=selected_image_title, use_column_width=True)
            st.write("Draw bounding boxes on the image to annotate.")
            
            # Placeholder for annotation (manual input)
            # For a production app, integrate a frontend annotation tool or use existing libraries.
            label = st.text_input(f"Label for {selected_image_title}", key=f"label_{selected_image_title}")
            x_min = st.number_input(f"x_min for {selected_image_title}", min_value=0, max_value=image.shape[1], key=f"x_min_{selected_image_title}")
            y_min = st.number_input(f"y_min for {selected_image_title}", min_value=0, max_value=image.shape[0], key=f"y_min_{selected_image_title}")
            x_max = st.number_input(f"x_max for {selected_image_title}", min_value=0, max_value=image.shape[1], key=f"x_max_{selected_image_title}")
            y_max = st.number_input(f"y_max for {selected_image_title}", min_value=0, max_value=image.shape[0], key=f"y_max_{selected_image_title}")

            if st.button(f"Save Annotation for {selected_image_title}"):
                # Validate coordinates
                if x_min >= x_max or y_min >= y_max:
                    st.error("Invalid coordinates: x_min must be less than x_max and y_min less than y_max.")
                    logging.warning(f"Invalid annotation coordinates for {selected_image_title}.")
                else:
                    annotation = {
                        'filename': selected_image_title,
                        'label': label,
                        'x_min': x_min,
                        'y_min': y_min,
                        'x_max': x_max,
                        'y_max': y_max
                    }
                    st.session_state['annotations'].append(annotation)
                    st.success(f"Annotation saved for {selected_image_title}")
                    logging.info(f"Annotation saved for {selected_image_title}: {annotation}")
    else:
        st.info("No images available for annotation. Please upload images using the sidebar.")

    # Button to save all annotations to Google Drive
    if st.button("Save All Annotations to Google Drive"):
        if st.session_state['annotations']:
            try:
                # Convert annotations to DataFrame
                df = pd.DataFrame(st.session_state['annotations'])
                # Save to a temporary CSV file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_csv:
                    df.to_csv(tmp_csv.name, index=False)
                    # Upload the CSV to Google Drive
                    upload_to_drive(drive, tmp_csv.name, GDRIVE_FOLDER_ID)
                    os.unlink(tmp_csv.name)
                st.success("All annotations uploaded to Google Drive.")
                logging.info("All annotations uploaded to Google Drive.")
                # Clear session state
                st.session_state['annotations'] = []
            except Exception as e:
                logging.error(f"Failed to upload annotations: {e}")
                st.error("Failed to upload annotations to Google Drive.")
        else:
            st.warning("No annotations to upload.")
            logging.warning("Attempted to upload annotations, but none were found.")

    st.markdown("---")
    st.write("Developed by [Your Name](https://yourwebsite.com)")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception("An unexpected error occurred in the Streamlit app.")
        st.error("An unexpected error occurred. Please check the logs for more details.")