import pandas as pd
import re
import json

COICOP_CATEGORIES_FILE= 'coicop_categories_no_services.csv'

def classify_products():
    """
    Classifies products from products.csv into COICOP categories from coicop_categories_no_services.csv.
    """
    try:
        products_df = pd.read_csv('products.csv')
        categories_df = pd.read_csv(COICOP_CATEGORIES_FILE)
    except FileNotFoundError as e:
        print(f"Error reading file: {e}. Make sure 'products.csv' and 'coicop_categories_no_services.csv' are in the correct directory.")
        return

    # Load special keywords
    try:
        with open('special_keywords.json', 'r') as f:
            special_keywords = json.load(f)
    except FileNotFoundError:
        print("Warning: special_keywords.json not found. Proceeding without special keywords.")
        special_keywords = {}

    # Prepare categories keywords for matching
    category_keywords = {}
    for _, row in categories_df.iterrows():
        # Remove punctuation and convert to set of words
        keywords = set(re.findall(r'\w+', str(row['keywords']).lower()))
        category_keywords[row['code']] = {
            'title': row['title'],
            'keywords': keywords
        }

    classified_data = []

    # Classify each product
    for _, product_row in products_df.iterrows():
        product_desc = str(product_row['product_w_cat']).lower()
        # Remove punctuation and get a set of words from the product description
        product_words = set(re.findall(r'\w+', product_desc.replace(';', ' ')))

        best_category_code = None
        max_score = -1

        for code, cat_data in category_keywords.items():
            # The score is the number of intersecting words
            score = len(product_words.intersection(cat_data['keywords']))
            
            # Simple title match check to break ties and improve accuracy
            # We give a boost if the product name contains words from the category title
            title_words = set(re.findall(r'\w+', str(cat_data['title']).lower()))
            if not product_words.isdisjoint(title_words):
                 score += 5 # Add a bonus for title match

            # Check for special keywords match
            if code in special_keywords:
                special_kw_set = set(kw.lower() for kw in special_keywords[code])
                if not product_words.isdisjoint(special_kw_set):
                    score += 20 # Add a bonus for special keywords match

            if score > max_score:
                max_score = score
                best_category_code = code

        if best_category_code:
            classified_data.append({
                'product_w_cat': product_row['product_w_cat'],
                'code': best_category_code,
                'title': category_keywords[best_category_code]['title']
            })
        else:
            classified_data.append({
                'product_w_cat': product_row['product_w_cat'],
                'code': 'N/A',
                'title': 'N/A'
            })

    # Create a new DataFrame for the classified products
    classified_df = pd.DataFrame(classified_data)

    # Save to a new CSV file
    classified_df.to_csv('classified.csv', index=False)
    print("Classification complete. Results saved to 'classified.csv'.")

if __name__ == "__main__":
    classify_products()
