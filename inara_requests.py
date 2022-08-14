import pprint

import requests
from bs4 import BeautifulSoup


def inara_find_fc_system(fcid):
    # print("Searching inara for carrier %s" % ( fcid ))
    URL = "https://inara.cz/station-market/?search=%s" % (fcid)
    # URL = "https://inara.cz/search/?search=%s" % ( fcid )
    try:
        page = requests.get(URL, headers={'User-Agent': 'PTNStockBot'})
        soup = BeautifulSoup(page.content, "html.parser")
        header = soup.find_all("div", class_="headercontent")
        header_info = header[0].find("h2")
        carrier_system_info = header_info.find_all('a', href=True)
        carrier = carrier_system_info[0].text
        system = carrier_system_info[1].text

        if fcid in carrier:
            # print("Carrier: %s (stationid %s) is at system: %s" % (carrier.text, stationid['href'][9:-1], system))
            return {'system': system, 'stationid': carrier_system_info[0]['href'][15:-1], 'full_name': carrier}
        else:
            print("Could not find exact match, aborting inara search")
            return False
    except Exception as e:
        print("No results from inara for %s, aborting search. Error: %s" % (fcid, e))
        return False


def inara_fc_market_data(fcid):
    # print("Searching inara market data for station: %s (%s)" % ( stationid, fcid ))
    try:
        URL = "https://inara.cz/station-market/?search=%s" % (fcid)
        page = requests.get(URL, headers={'User-Agent': 'PTNStockBot'})
        soup = BeautifulSoup(page.content, "html.parser")
        mainblock = soup.find_all('div', class_='mainblock')

        # Find carrier and system info
        header = soup.find_all("div", class_="headercontent")
        header_info = header[0].find("h2")
        carrier_system_info = header_info.find_all('a', href=True)
        carrier = carrier_system_info[0].text
        system = carrier_system_info[1].text

        # Find market info
        updated = soup.find("div", text="Market update").next_sibling.get_text()
        # main_content = soup.find('div', class_="maincontent0")
        table = mainblock[1].find('table')
        tbody = table.find("tbody")
        rows = tbody.find_all('tr')
        marketdata = []
        for row in rows:
            rowclass = row.attrs.get("class") or []
            if "subheader" in rowclass:
                continue
            cells = row.find_all("td")
            rn = cells[0].get_text()
            commodity = {
                'id': rn,
                'name': rn,
                'sellPrice': int(cells[1].get_text().replace('-', '0').replace(',', '').replace(' Cr', '')),
                'buyPrice': int(cells[2].get_text().replace('-', '0').replace(',', '').replace(' Cr', '')),
                'demand': int(cells[3].get_text().replace('-', '0').replace(',', '')),
                'stock': int(cells[4].get_text().replace('-', '0').replace(',', ''))
            }
            marketdata.append(commodity)
        data = {}
        data['name'] = system
        data['currentStarSystem'] = system
        data['full_name'] = carrier
        data['sName'] = fcid
        data['market_updated'] = updated
        data['commodities'] = marketdata
        return data
    except Exception as e:
        print("Exception getting inara data for carrier: %s" % fcid)
        return False

