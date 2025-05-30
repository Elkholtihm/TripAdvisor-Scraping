import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import random
from selenium.webdriver.common.action_chains import ActionChains
import pandas as pd
import os
import requests
from fake_useragent import UserAgent



def plus_petit_superieur(nbr_restau):
    return (nbr_restau // 30) * 30

def ScrapRestau(driver):
    # Charger les données existantes
    try:
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'Restaurants.csv')
        df = pd.read_csv(csv_path)
        existing_links = set(df['link'].tolist())  # Stocker les liens existants pour éviter les doublons
        nbr_restau = df.shape[0]
    except FileNotFoundError:
        existing_links = set()
        nbr_restau = 0

    # Charger la dernière page
    try:
        with open('checkpoints/last_page.txt', 'r') as f:
            last_page = int(f.read().strip())
    except FileNotFoundError:
        last_page = plus_petit_superieur(nbr_restau)

    print(f"Starting from page {last_page}")

    # Ouvrir WebDriver
    driver.get(f"https://www.tripadvisor.fr/Restaurants-g32655-oa{last_page}-Los_Angeles_California.html")
    time.sleep(5)

    counter = 0

    while counter < 500 - nbr_restau:
        print(f'Scraping page {last_page}...')

        time.sleep(random.uniform(3, 6))
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # Récupérer le contenu HTML
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # Trouver les liens des restaurants
            elements = soup.find_all('a', href=True)

            new_restaurants = []
            restaurant_dict = {}
            capturing_restaurant = False  

            for elem in elements:
                if "/Restaurant_Review-" in elem['href']:
                    text = elem.get_text().strip()

                    # Ignorer les boutons inutiles
                    if any(keyword in text.lower() for keyword in ["réserver", "commander en ligne", "trouver une table"]):
                        continue  

                    if "avis" in text.lower():  
                        restaurant_dict["avis"] = text  
                    else:  
                        if text.strip():  # Vérifier si le nom du restaurant est valide
                            if "name" in restaurant_dict and "link" in restaurant_dict and "avis" in restaurant_dict:
                                if restaurant_dict["avis"] != "N/A" and restaurant_dict["link"] not in existing_links:
                                    new_restaurants.append(restaurant_dict)
                                    existing_links.add(restaurant_dict["link"])  # Éviter les doublons

                            restaurant_dict = {"name": text, "avis": "N/A"}
                            capturing_restaurant = True  

                    if capturing_restaurant:
                        restaurant_dict["link"] = "https://www.tripadvisor.fr" + elem['href']
                        capturing_restaurant = False  

            if "name" in restaurant_dict and "link" in restaurant_dict and "avis" in restaurant_dict:
                if restaurant_dict["avis"] != "N/A" and restaurant_dict["link"] not in existing_links:
                    new_restaurants.append(restaurant_dict)
                    existing_links.add(restaurant_dict["link"])  

            # 🛠 Vérification du nombre de restaurants trouvés
            print(f"Nombre de restaurants extraits : {len(new_restaurants)}")

            # Sauvegarde dans CSV avec vérification de l'en-tête
            file_empty = not os.path.exists(csv_path) or os.stat(csv_path).st_size == 0
            df = pd.DataFrame(new_restaurants)
            df.to_csv(csv_path, mode='a', index=False, header=file_empty)

            time.sleep(random.uniform(4, 7))

            # Passer à la page suivante
            next_button = driver.find_element(By.XPATH, "//a[contains(@aria-label, 'Page suivante')]")

            actions = ActionChains(driver)
            actions.move_to_element(next_button).click().perform()

            time.sleep(5)
            last_page += 30  

            with open('checkpoints/last_page.txt', 'w') as f:
                f.write(str(last_page))

        except Exception as e:
            print(f"Erreur ou blocage : {e}")
            print("Sauvegarde des progrès et sortie...")
            df = pd.DataFrame(new_restaurants)
            df.to_csv(csv_path, mode='a', index=False, header=False)  
            break  

    driver.quit()


def ScrapUsers():
    # File paths
    csv_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'Restaurants.csv')
    last_index_file = 'checkpoints/last_restaurant.txt'
    output_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'user.csv')

    # Read last processed index
    try:
        with open(last_index_file, 'r') as f:
            last_index = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        last_index = -1  # Start from the beginning

    # Read CSV file
    df = pd.read_csv(csv_file)

    # Base URL for TripAdvisor
    base_url = "https://www.tripadvisor.com"

    # Check if output file exists (to avoid re-adding headers)
    file_exists = os.path.exists(output_file)

    # Iterate through restaurants
    for index, row in df.iterrows():
        if index <= last_index:
            continue  # Skip already processed ones

        restaurant_name = row["name"]
        restaurant_url = row["link"]

        # Generate new User-Agent for each request
        headers = {
            "User-Agent": UserAgent().random,
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
            "DNT": "1",
            "Connection": "keep-alive",
        }

        # Handle connection errors
        try:
            response = requests.get(restaurant_url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"⚠ Failed to retrieve {restaurant_name} (Status: {response.status_code})")
                continue
        except requests.RequestException as e:
            print(f"🚨 Request error for {restaurant_name}: {e}")
            continue

        # Parse HTML
        soup = BeautifulSoup(response.text, "html.parser")
        users_infos = soup.find_all("div", class_="_c")

        # Collect reviews
        reviews = []
        for user_infos in users_infos:
            try:
                user_element = user_infos.find("a", class_="BMQDV _F Gv wSSLS SwZTJ FGwzt ukgoS")
                user_name = user_element.text if user_element else "no name"
            except AttributeError:
                user_name = "no name"

            try:
                location_element = user_infos.find("div", class_="biGQs _P pZUbB osNWb")
                location = location_element.find("span").text if location_element else "no location"
            except AttributeError:
                location = "no location"

            try:
                review_title_div = user_infos.find("div", class_="biGQs _P fiohW qWPrE ncFvv fOtGX")
                review_title = review_title_div.find("a").text if review_title_div else "no review title"
            except AttributeError:
                review_title = "no review title"

            try:
                review = user_infos.find("span", class_="JguWG").text
            except AttributeError:
                review = "no review"

            try:
                date = user_infos.find("div", class_="aVuQn").text
            except AttributeError:
                date = "no date"

            try:
                rating_element = user_infos.find("svg", class_="UctUV d H0")
                rating = rating_element.find("title").text if rating_element else "no rating"
            except AttributeError:
                rating = "no rating"

            try:
                user_element = user_infos.find("a", class_="BMQDV _F Gv wSSLS SwZTJ FGwzt ukgoS")
                user_profile_link = base_url + user_element['href'].strip() if user_element and user_element.has_attr('href') else "no link"
            except (AttributeError, TypeError):
                user_profile_link = "no link"

            reviews.append({
                "restaurant_name": restaurant_name,
                "user_name": user_name,
                "location": location,
                "review_title": review_title,
                "review": review,
                "date": date,
                "rating": rating,
                "user_profile_link": user_profile_link  
            })
            print(f'{user_name} processed for {restaurant_name}')

        # Save reviews
        df_reviews = pd.DataFrame(reviews)
        df_reviews.to_csv(output_file, mode='a', index=False, header=not file_exists)
        file_exists = True  # Ensure header isn't written again

        # Save last processed index
        with open(last_index_file, 'w') as f:
            f.write(str(index))

        print(f"✅ Saved reviews for {restaurant_name}.\n")

        # Sleep to avoid getting blocked
        time.sleep(2)  