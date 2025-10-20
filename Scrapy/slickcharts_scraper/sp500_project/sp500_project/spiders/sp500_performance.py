# sp500_project/spiders/sp500_performance.py
import scrapy
from ..items import Sp500ProjectItem

class Sp500PerformanceSpider(scrapy.Spider):
    name = 'sp500_performance'
    allowed_domains = ['slickcharts.com']
    start_urls = ['https://www.slickcharts.com/sp500/performance']

    custom_settings = {
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
    }

    def parse(self, response):
        xpath_selector = '//table[contains(@class, "table-borderless") and contains(@class, "table-sm")]//tbody/tr'
        rows = response.xpath(xpath_selector)

        self.logger.info(f"Found {len(rows)} rows with XPath.")

        if len(rows) < 10:
            self.logger.warning("Fewer than 10 rows found. Check table selector.")
            snippet = response.text[:800].replace('\n', ' ')
            self.logger.debug(f"HTML snippet: {snippet}")
            return

        for row in rows:
            item = Sp500ProjectItem()
            item['number'] = row.xpath('./td[1]/text()').get(default='').strip()
            company_text = row.xpath('./td[2]/a/text() | ./td[2]/text()').get()
            item['company'] = company_text.strip() if company_text else None
            item["symbol"] = "".join(row.xpath("./td[3]//text()").getall()).strip()
            item['ytd_return'] = row.xpath('./td[4]/text()').get(default='').strip()

            if item['company']:
                yield item
