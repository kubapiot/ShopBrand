import streamlit as st
import pandas as pd
import os
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode


st.set_page_config(layout="wide")
# Create a Streamlit app
st.title('ChatGPT Output Data')

# Create two columns
col1, col2 = st.columns(2)

# Load the CSV data
df = pd.read_csv('chatgpt_output.csv')



# Display site grid with AgGrid
st.subheader("All Sites")
with col1:
    site_grid = df[['SiteID', 'hasShop', 'shopBrand', 'accuracy', 'Tokens']].reset_index(drop=True)

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
# Check if a row is selected
selected_rows = grid_response.get('selected_rows', [])
if len(selected_rows) > 0:
    selected_row = selected_rows
    site_id = str(selected_rows['SiteID'].values[0])  # Assumes 'SiteID' is a column in your CSV
    image_folder = 'static/images'

    # Search for and display images matching the SiteID
    with col2:
        images_found = False
        for filename in os.listdir(image_folder):
            if filename.startswith(str(site_id) + '_'):
                image_path = os.path.join(image_folder, filename)
                st.image(image_path, caption=filename)
                images_found = True

    if not images_found:
        st.warning(f"No images found for SiteID: {site_id}")

