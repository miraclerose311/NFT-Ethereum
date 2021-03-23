import datetime
import csv
from nearest_dict import NearestDict
from etherscan import etherscan_gas, etherscan_timestamp
import requests

def read_csv(fn):
    with open(fn) as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            yield row

class EthereumFootprint():
    """
    Load the energy estimate from Digiconomist, and the gas
    measurement from Etherscan. Add some overhead like Offsetra.
    kgCO2/kWh is based on global 2019 mining pool distribution.
    """
    def __init__(self,
        date_to_kwh_fn='data/EECI_TWh - TWh per Year.csv',
        date_to_gas_fn='data/export-GasUsed.csv',
        kgco2_per_kwh=0.486,
        overhead=1.20):

        self.kgco2_per_kwh = kgco2_per_kwh
        self.overhead = overhead

        # https://digiconomist.net/ethereum-energy-consumption/
        date_to_kwh = {}
        for date, est_twh, min_twh in read_csv(date_to_kwh_fn):
            date = datetime.datetime.strptime(date, '%Y/%m/%d').date()
            try:
                # convert TWh/year to KWh/day
                kwh = 1e9 * float(est_twh) / 365
                date_to_kwh[date] = kwh
            except ValueError:
                continue
        self.date_to_kwh = NearestDict(date_to_kwh)

        # https://etherscan.io/chart/gasused?output=csv
        self.get_etherscan_data()
        date_to_gas = {}
        for date, timestamp, gas in read_csv('data/export-GasUsed.csv'):
            date = datetime.datetime.strptime(date, '%m/%d/%Y').date()
            date_to_gas[date] = int(gas)
        self.date_to_gas = NearestDict(date_to_gas)

    def kgco2_per_gas(self, date):
        # weighted emissions factor based on mining pool distribution in 2019
        kwh_per_gas = self.date_to_kwh[date] / self.date_to_gas[date]
        return self.overhead * self.kgco2_per_kwh * kwh_per_gas

    def sum_kgco2(self, transactions, start_date=None, end_date=None):
        kgco2 = 0
        for tx in transactions:
            date = etherscan_timestamp(tx).date()
            if start_date is not None and date < start_date:
                continue
            if end_date is not None and date >= end_date:
                continue
            gas = etherscan_gas(tx)
            kgco2 += self.kgco2_per_gas(date) * gas
        return kgco2

    def get_etherscan_data(self):
        # replaces export-GasUsed.csv each time run
        url = 'https://etherscan.io/chart/gasused?output=csv'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36'}

        etherscan_response = requests.get(url, headers=headers)

        with open('data/export-GasUsed.csv', 'w') as file:
            file.write(etherscan_response.content.decode())