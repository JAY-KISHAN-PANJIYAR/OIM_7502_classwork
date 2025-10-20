# sp500_project/items.py
import scrapy

class Sp500ProjectItem(scrapy.Item):
    # Required fields from the assignment
    number = scrapy.Field()       # Column 1: Rank/Number
    company = scrapy.Field()      # Column 2: Company Name
    symbol = scrapy.Field()       # Column 3: Ticker Symbol
    ytd_return = scrapy.Field()   # Column 4: YTD Return