import requests
import streamlit as st
import pandas as pd
import os
import json
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials
from streamlit_gsheets import GSheetsConnection

service_account_info = json.loads(st.secrets["SERVICE_ACCOUNT_JSON"])
google_api_key = st.secrets["GOOGLE_KEY"]

# Authenticate using the service account JSON
SCOPES = ['https://www.googleapis.com/auth/drive']
credentials = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
service = build('drive', 'v3', credentials=credentials)


# Specify the folder ID
#FOLDER_ID = '1dWsz0Er13-odiXI4OQ6N_Exqg0UVxTS3'
FOLDER_ID = '19ZZ65cWpn6mfrFTNRROjseuuxK-nnYUm'

# Query to get files in the specific folder

def display_street_view(latitude, longitude,heading,pitch):
    iframe_html = f"""
    <iframe
    width="600"
    height="450"
    style="border:0"
    loading="lazy"
    allowfullscreen
    referrerpolicy="no-referrer-when-downgrade"
    src="https://www.google.com/maps/embed/v1/streetview?key={google_api_key}&location={latitude},{longitude}&heading={heading}&pitch={pitch}&fov=80">
    </iframe>
    """
    st.components.v1.html(iframe_html, height=600)

st.set_page_config(layout="wide")
# Create a Streamlit app
st.title('ChatGPT Output Data')

# Create two columns
col1, col2 = st.columns(2)

# Load the CSV data
df = pd.read_csv('gemini_output.csv')
#df_sites = pd.read_csv('streetview_uk_updated.csv')
conn = st.connection("gsheets", type=GSheetsConnection)
df_sites = conn.read()

# Define function to get image URLs based on SiteID
def get_images(siteid):
    query = f"'{FOLDER_ID}' in parents and name contains '{siteid}' and trashed = false"

    # Retrieve files
    results = service.files().list(
        q=query,
        fields="files(id, name)"
    ).execute()

    files = results.get('files', [])
    image_urls = []

    if files:
        for file in files:
            #file_url = f"https://drive.google.com/file/d/{file['id']}/view"
            file_url = f"https://drive.google.com/uc?export=view&id={file['id']}"

            image_urls.append((file['name'], file_url))
    return image_urls

# Display site grid with AgGrid

with col1:
    site_grid = df[['SiteID','NetWatchBrand',  'hasShop', 'shopBrand', 'accuracy', 'Tokens']].reset_index(drop=True)

    # Define dropdown options for `shopBrand`
    brand_options = sorted(df['shopBrand'].dropna().unique().tolist())
    

    # Configure AgGrid options
    gb = GridOptionsBuilder.from_dataframe(site_grid)
    gb.configure_selection(
        selection_mode="single",  # Single row selection
        use_checkbox=False  # Disable checkbox for selection
    )
    gb.configure_grid_options(
        suppressRowClickSelection=False,  # Allow selection by clicking any cell
        rowSelection='single',  # Enable single-row selection
        suppressMovableColumns=True  # Keep columns fixed
    )

    # Configure editable column with autocomplete
    gb.configure_column(
        "new_brand",
        editable=True,
        cellEditor="agRichSelectCellEditor",  # Use AgGrid's rich select editor
        cellEditorParams={
            "values": brand_options,  # Provide autocomplete options
            "filter": True,  # Enable filtering for dropdown
            "debounceMs": 200,  # Optional: debounce for filtering
        },
    )


    # Add JS code to handle row selection when navigating with the arrow keys
    custom_js = """
    function onRowSelected(event) {
        const selectedNode = event.api.getSelectedNodes()[0];
        if (selectedNode) {
            const selectedData = selectedNode.data;
            return selectedData;
        }
        return null;
    }
    """
    gb.configure_grid_options(onRowSelected=custom_js)
    grid_options = gb.build()

     # Render the grid
    grid_response = AgGrid(
        site_grid,
        gridOptions=grid_options,
        height=300,
        allow_unsafe_jscode=True,  # Allow unsafe JS code
        theme='streamlit',
        enable_enterprise_modules=True  # Enable advanced features like keyboard navigation
    )
    
    # Save changes to Google Sheets
    if st.button("Save Changes"):
        sheet_name = "Sheet1"
        # Access updated DataFrame after user interaction
        updated_df = pd.DataFrame(grid_response['data'])
        # Reset index to align DataFrames
        updated_df = updated_df.reset_index(drop=True)
        df = df.reset_index(drop=True)

        # Compare columns to find changes
        changes = updated_df[updated_df['new_brand'] != df['shopBrand']]

        if not changes.empty:
            for _, row in changes.iterrows():
                site_id = row['SiteID']
                new_brand = row['new_brand']
                # Get the index of the row you want to update
                row_index = df_sites[df_sites['siteid'] == int(site_id)].index[0]

                # Update the specific cell
                df_sites.at[row_index, 'shopBrand'] = new_brand
            # Overwrite the Google Sheet with the updated DataFrame
            conn.update(data=df_sites.to_dict(orient='records'))
        else:
            st.info("No changes detected.")

        # Read the original CSV file
        original_df = pd.read_csv('gemini_output.csv')

        # Update the original DataFrame with the new brand information
        for _, row in changes.iterrows():
            site_id = row['SiteID']
            new_brand = row['new_brand']
            original_df.loc[original_df['SiteID'] == site_id, 'shopBrand'] = new_brand

        # Write the updated DataFrame back to the CSV file
        original_df.to_csv('gemini_output.csv', index=False)
   
# Check if a row is selected
selected_rows = grid_response.get('selected_rows', [])
if not selected_rows is None and len(selected_rows) > 0:
    selected_row = selected_rows
    site_id = str(selected_rows['SiteID'].values[0])  # Assumes 'SiteID' is a column in your CSV
    image_folder = 'static/images'

    # Search for and display images matching the SiteID
    with col2:
        st.subheader("Street View")
        latitude = df_sites.loc[df_sites['siteid'] == int(site_id)]['latitude'].iloc[0]
        longitude = df_sites.loc[df_sites['siteid'] == int(site_id)]['longitude'].iloc[0]
        heading = df_sites.loc[df_sites['siteid'] == int(site_id)]['heading'].iloc[0]
        pitch = df_sites.loc[df_sites['siteid'] == int(site_id)]['pitch'].iloc[0]
        display_street_view(latitude, longitude,heading,pitch)

        st.subheader(f"Images for SiteID: {site_id}")
        image_urls = get_images(site_id)

        if image_urls:
            for name, url in image_urls:
                response = requests.get(url)
                st.image(response.content)
        else:
            st.warning(f"No images found for SiteID: {site_id}")
