from typing import Any
import csv
import datetime
import json
import math
import os
import time

from bs4 import BeautifulSoup
from dotenv import find_dotenv, load_dotenv
import pytz
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import tweepy

load_dotenv(find_dotenv())


lbj_site_link = "https://www.basketball-reference.com/players/j/jamesle01/gamelog/{}"
kareem_link = "https://www.basketball-reference.com/players/a/abdulka01/gamelog/{}"
malone_link = "https://www.basketball-reference.com/players/m/malonka01/gamelog/{}"


options = Options()
options.headless = True
driver = webdriver.Chrome(options=options)


def get_soup(s: Any) -> BeautifulSoup:
    return BeautifulSoup(str(s), "html.parser")


def get_stats_table_headers(page_soup: BeautifulSoup) -> tuple[dict, list]:
    scoring_table = page_soup.find_all("table", "row_summable")
    if len(scoring_table) != 1:
        if len(scoring_table) == 2:
            scoring_table = scoring_table[0]
        else:
            print("Scoring table should only be one. This is probably because of playoff")

    table_soup = get_soup(scoring_table)

    headers = table_soup.find("thead")

    header_soup = get_soup(headers)
    header_vals = {}
    for idx, col in enumerate(header_soup.find_all("th")):
        header_vals[col.get_text()] = idx

    body = table_soup.find("tbody")
    body_soup = get_soup(body)
    datum = body_soup.find_all("tr")

    data_raw = []
    for idx, data in enumerate(datum):
        row_soup = get_soup(data)
        cells = [c.get_text() for c in row_soup.find_all("td")]
        cells.insert(0, idx + 1)
        if len(cells) > 1 and "Inactive" not in cells:
            if (
                "Inactive" in cells
                or "Did Not Dress" in cells
                or "Not With Team" in cells
                or "Did Not Play" in cells
                or "Player Suspended" in cells
            ):
                continue
            else:
                data_raw.append(cells)

    return header_vals, data_raw


def add_pts_to_map(headers: dict, data_raw: list, point_list: list, pt_map: dict = None) -> tuple[list, datetime.datetime]:
    pts_col = headers["PTS"]
    point_list.append(int(data_raw[pts_col]))

    last_game = None
    if pt_map is not None:
        d = date_parse(data_raw[headers["Date"]])
        last_game = datetime.datetime.strptime(data_raw[headers["Date"]], "%Y-%m-%d")
        if d not in pt_map.keys():
            pt_map[str(d)] = int(data_raw[pts_col])

    return point_list, last_game


# First let's convert the date to a number
def date_parse(d: str) -> int:
    START_DATE = datetime.date(1900, 1, 1)
    d1 = datetime.datetime.strptime(d, "%Y-%m-%d")
    d1 = d1.date()
    d1 = d1 - START_DATE
    return d1.days


def get_lebron_pts() -> tuple[bool, list, datetime.datetime]:
    """Returns true if entries are added to the lbj_pt_map"""
    lbj_pt_map = {}

    # We can check for the json file then we only have to regenerate the last year

    point_list = []
    try:
        with open("lbj.json", "r") as f:
            lbj_pt_map = json.load(f)
            print("Able to read data from lbj.json")
        os.remove("lbj.json")  # remove it because we will write a new one
    except:
        print("lbj.json probably does not exist")

    start_size = len(lbj_pt_map)

    if len(lbj_pt_map) > 0:
        for k in lbj_pt_map:
            point_list.append(lbj_pt_map[k])

    start_year = 2004 if len(lbj_pt_map) == 0 else 2022

    last_game = None
    for year in range(start_year, 2023):
        driver.get(lbj_site_link.format(year))
        page_soup = get_soup(driver.page_source)
        header_vals, data_raw = get_stats_table_headers(page_soup)

        for l in data_raw:
            try:
                point_list, last_game = add_pts_to_map(header_vals, l, point_list, pt_map=lbj_pt_map)
            except:
                print(l)

    ret = []
    for k in lbj_pt_map:
        ret.append(lbj_pt_map[k])

    # Now let's write the lbj_pt_map to a json file
    with open("lbj.json", "w") as f:
        json.dump(lbj_pt_map, f, indent=4)

    return len(lbj_pt_map) != start_size, ret, last_game


def get_kareem_pts():
    # First we'll check for the 'kareem.csv' file
    try:
        data = read_csv_to_list("kareem.csv")
        print("Read data from saved kareem.csv")
        return data
    except:
        pass

    point_list = []
    for year in range(1970, 1990):
        driver.get(kareem_link.format(year))
        page_soup = get_soup(driver.page_source)
        header_vals, data_raw = get_stats_table_headers(page_soup)

        for l in data_raw:
            try:
                point_list = add_pts_to_map(header_vals, l, point_list)
            except:
                print(l)

    save_list_to_file(point_list, "kareem.csv")
    return point_list


def get_malone_pts():
    # First we'll check for the 'malone.csv' file
    try:
        data = read_csv_to_list("malone.csv")
        print("Read data from saved malone.csv")
        return data
    except:
        pass

    point_list = []
    for year in range(1986, 2005):
        driver.get(malone_link.format(year))
        page_soup = get_soup(driver.page_source)
        header_vals, data_raw = get_stats_table_headers(page_soup)

        for l in data_raw:
            try:
                point_list = add_pts_to_map(header_vals, l, point_list)
            except:
                print(l)

    save_list_to_file(point_list, "malone.csv")
    return point_list


def save_list_to_file(data: list, file_name: str) -> None:
    with open(file_name, "w") as f:
        writer = csv.writer(f)
        writer.writerow(data)


def read_csv_to_list(file_name: str) -> list:
    with open(file_name, "r") as f:
        reader = csv.reader(f)
        for data in reader:
            return [int(d) for d in data]
    return []


def cumulative_points(point_list: list) -> list:
    cum_pts = [point_list[0]]
    for idx, p in enumerate(point_list[1:]):
        # the idx already has the '-1' portion because we're starting at the first entry
        cum_pts.append(cum_pts[idx] + p)
    return cum_pts


def create_plot(lbj_point_list, kareem_point_list, malone_point_list):
    print("Creating a new graph")

    import matplotlib.pyplot as plt

    lbj_cumulative = cumulative_points(lbj_point_list)
    kareem_cumulative = cumulative_points(kareem_point_list)
    malone_cumulative = cumulative_points(malone_point_list)

    plt.plot([i for i in range(1, len(kareem_point_list) + 1)], kareem_cumulative, label="Kareem")
    plt.plot([i for i in range(1, len(malone_point_list) + 1)], malone_cumulative, label="Malone")
    plt.plot([i for i in range(1, len(lbj_point_list) + 1)], lbj_cumulative, label="LeBron")
    plt.plot(
        [i for i in range(1, len(malone_point_list) + 1)],
        [malone_cumulative[-1] for _ in range(1, len(malone_point_list) + 1)],
        label="Malone Total",
    )
    plt.plot(
        [i for i in range(1, len(kareem_point_list) + 1)],
        [kareem_cumulative[-1] for _ in range(1, len(kareem_point_list) + 1)],
        label="Kareem Total",
    )
    plt.plot(
        [i for i in range(1, len(lbj_point_list) + 1)],
        [lbj_cumulative[-1] for _ in range(1, len(lbj_point_list) + 1)],
        label="Lebron Total",
    )
    plt.legend()
    plt.savefig(f"graph_{datetime.datetime.today().strftime('%Y-%m-%d')}.png")


def get_table_headers(soup: BeautifulSoup) -> dict:
    headers = soup.find("thead")
    header_soup = get_soup(headers)

    header_vals = {}
    for idx, col in enumerate(header_soup.find_all("th")):
        header_vals[col.get_text()] = idx

    return header_vals


def get_laker_schedule(driver: webdriver.Chrome) -> None:
    laker_schedule_link = "https://www.basketball-reference.com/teams/LAL/{}_games.html".format(
        datetime.datetime.today().year
    )
    driver.get(laker_schedule_link)

    page_soup = get_soup(driver.page_source)

    table = page_soup.find_all("table", "sortable")
    if len(table) > 1:
        print("Table should only be one")
        table = table[0]
    table_soup = get_soup(table)

    headers = get_table_headers(table_soup)

    body = table_soup.find("tbody")
    body_soup = get_soup(body)
    datum = body_soup.find_all("tr")

    laker_schedule = []
    for data in datum:
        row_soup = get_soup(data)
        cells = [c.get_text() for c in row_soup.find_all("td")]

        if len(cells) > 1:
            date, time, at, opponent = cells[0], cells[1], cells[4], cells[5]

            d1 = datetime.datetime.strptime(date, "%a, %b %d, %Y")
            if d1 > datetime.datetime.today():
                laker_schedule.append((d1.strftime("%m-%d-%Y"), time, at, opponent))

    return laker_schedule


def send_tweet(tweet_str: str, last_game: datetime.datetime) -> None:
    consumer_key = os.environ["TWITTER_CONSUMER_KEY"]
    consumer_secret = os.environ["TWITTER_CONSUMER_KEY_SECRET"]
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)

    access_token = os.environ["ACCOUNT_ACCESS_TOKEN"]
    access_token_secret = os.environ["ACCOUNT_ACCESS_TOKEN_SECRET"]
    auth.set_access_token(access_token, access_token_secret)

    api = tweepy.API(auth)

    api.verify_credentials()

    if len(tweet_str) > 280:
        print(tweet_str)
        print("TWEET IS TOO LONG, UPDATE MANUALLY")

    if should_send_tweet(api, last_game):
        if len(tweet_str) < 280:
            api.update_status(tweet_str)
            print("Sent tweet")
    else:
        print("Already tweeted today")


def should_send_tweet(api: tweepy.API, last_game: datetime.datetime) -> bool:
    latest_tweet_date = datetime.datetime.utcnow() - datetime.timedelta(days=365)
    latest_tweet_date = latest_tweet_date.replace(tzinfo=pytz.timezone('US/Eastern'))
    for tweet in api.user_timeline():
        created_at = tweet.created_at.replace(tzinfo=pytz.timezone('US/Eastern'))
        if created_at > latest_tweet_date:
            latest_tweet_date = created_at

    print(f"Last tweet was on {last_game.date()} and last game was on {latest_tweet_date.date()}")
    return last_game.date() >= latest_tweet_date.date()



def construct_tweet(lbj: int, kareem: int, malone: int, lebron_avg: float, schedule: list) -> str:
    tweet = ""
    tweet = "1. {}: {}\n2. {}: {}\n"
    if kareem > lbj:
        if malone > lbj:
            tweet = "1. Kareem: {}\n2. Malone: {}\n3. LeBron: {} ({} points back)\n".format(kareem, malone, lbj, malone - lbj)
            games = math.ceil((malone - lbj) / lebron_avg)
            game = schedule[games - 1]
            tweet += f"LeBron needs about {games} more games to pass Malone."
            tweet += f"\nBest guess for passing Malone is {'at' if game[2] == '@' else 'against'} {game[3]} on {game[0]} at {game[1]}"
        else:
            tweet = "1. Kareem: {}\n2. LeBron: {} ({} points back)\n".format(kareem, lbj, kareem - lbj)
            games = math.ceil((kareem - lbj) / lebron_avg)
            tweet += f"LeBron needs about {games} more games to pass Kareem."
            if games > len(schedule):
                tweet += "\nBest guess for passing Kareem is next season."
            else:
                game = schedule[games - 1]
                tweet += f"\nBest guess for passing Kareem is {'at' if game[2] == '@' else 'against'} {game[3]} on {game[0]} at {game[1]}"

    return tweet


if __name__ == "__main__":
    start = time.time()

    schedule = get_laker_schedule(driver)

    kareem_point_list = get_kareem_pts()
    malone_point_list = get_malone_pts()
    lbj_played, lbj_point_list, last_game = get_lebron_pts()

    kareem_total = sum(kareem_point_list)

    malone_total = sum(malone_point_list)

    lbj_total = sum(lbj_point_list)
    print("LBJ: ", lbj_total)

    # Let's see how long it will take LBJ to catch malone and kareem given his last 25 games

    malone_game_count = []
    kareem_game_count = []

    for rolling_avg in [10, 25, 100, len(lbj_point_list)]:
        avg = sum(lbj_point_list[len(lbj_point_list) - rolling_avg :]) / rolling_avg

        malone_game_count.append(math.ceil((malone_total - lbj_total) / avg))
        kareem_game_count.append(math.ceil((kareem_total - lbj_total) / avg))

    malone_game = None
    kareem_game = None
    if malone_total > lbj_total:
        median_game = int(sum(malone_game_count) / len(malone_game_count))
        if median_game < len(schedule):
            malone_game = schedule[median_game]
    elif kareem_total > lbj_total:
        median_game = int(sum(kareem_game_count) / len(kareem_game_count))
        if median_game < len(schedule):
            kareem_game = schedule[median_game]

    tweet_str = construct_tweet(
        lbj_total, kareem_total, malone_total, sum(lbj_point_list) / len(lbj_point_list), schedule
    )

    if len(tweet_str) + len("\n#NBA #LeBron #GOAT") < 280:
        tweet_str += "\n#NBA #LeBron #GOAT"

    print(f"TWEET:\n{tweet_str}")

    send_tweet(tweet_str, last_game)

    # Let's create a graph on mondays. I'm disabling this for now, I don't like the graph that much
    if datetime.datetime.today().weekday() == 7:
        create_plot(lbj_point_list, kareem_point_list, malone_point_list)

    print(f"Finished LBJ bot in {time.time() - start} seconds.")
    driver.close()
