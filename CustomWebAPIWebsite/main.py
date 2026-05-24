import os
import requests
from dotenv import load_dotenv
import cloudmersive_barcode_api_client
from cloudmersive_barcode_api_client.rest import ApiException

load_dotenv()

IMAGE_PATH = "barcode.jpg"


def main():
    # --- Step 1: Cloudmersive — scan barcode from image ---
    configuration = cloudmersive_barcode_api_client.Configuration()
    configuration.api_key['Apikey'] = os.getenv('API_KEYS')
    scan_api = cloudmersive_barcode_api_client.BarcodeScanApi(
        cloudmersive_barcode_api_client.ApiClient(configuration)
    )

    print(f"Scanning {IMAGE_PATH} ...")
    try:
        result = scan_api.barcode_scan_image(IMAGE_PATH)
    except ApiException as e:
        print(f"Cloudmersive error: {e}")
        return

    if not result.successful:
        print("Barcode not recognized.")
        return

    barcode = result.raw_text
    print(f"Barcode found: {barcode}")

    # --- Step 2: Open Food Facts — look up product by barcode ---
    print(f"Looking up product on Open Food Facts ...")
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    response = requests.get(url, headers={"User-Agent": "MyPortfolioApp/1.0"}, timeout=10)
    data = response.json()

    if data.get("status") != 1:
        print(f"Product not found for barcode {barcode}.")
        return

    product = data["product"]
    print(f"Name    : {product.get('product_name', 'N/A')}")
    print(f"Brand   : {product.get('brands', 'N/A')}")
    print(f"Category: {product.get('categories', 'N/A')}")
    print(f"Quantity: {product.get('quantity', 'N/A')}")


if __name__ == "__main__":
    main()
