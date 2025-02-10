from time import sleep
from bs4 import BeautifulSoup
from requests import get
from urllib.parse import unquote
from dateutil.parser import parse, ParserError
from .user_agents import get_useragent  # Ensure your package structure supports this import


def format_date(date_input: str) -> str:
    """
    Parse a date input string and return it in mm/dd/yyyy format.
    
    Parameters:
        date_input (str): A date in any common format (e.g., "10-20-2004", "2004-10-20", "October 20, 2004").
        
    Returns:
        str: Date formatted as mm/dd/yyyy.
        
    Raises:
        ValueError: If the date cannot be parsed.
    """
    try:
        dt = parse(date_input)
        return dt.strftime("%m/%d/%Y")
    except ParserError as e:
        raise ValueError(f"Could not parse date input: {date_input}") from e


def get_date_range_tbs(start_date: str = None, end_date: str = None) -> str:
    """
    Construct the 'tbs' parameter for Google search to filter by a custom date range.
    
    Parameters:
        start_date (str, optional): The starting date.
        end_date (str, optional): The ending date.
        
    Returns:
        str: A string in the format required by Google (e.g., "cdr:1,cd_min:10/20/2004,cd_max:10/20/2004").
             If neither date is provided, returns None.
    """
    if start_date or end_date:
        # If only one date is provided, use it for both min and max.
        if not start_date:
            start_date = end_date
        if not end_date:
            end_date = start_date

        start_date_formatted = format_date(start_date)
        end_date_formatted = format_date(end_date)
        return f"cdr:1,cd_min:{start_date_formatted},cd_max:{end_date_formatted}"
    return None


def _req(term, results, lang, start, proxies, timeout, safe, ssl_verify, region, tbs=None):
    """
    Internal function to make a GET request to Google Search.
    Adds the custom 'tbs' parameter if provided.
    """
    params = {
        "q": term,
        "num": results + 2,  # Extra results help prevent missing some items
        "hl": lang,
        "start": start,
        "safe": safe,
        "gl": region,
    }
    if tbs:
        params["tbs"] = tbs

    resp = get(
        url="https://www.google.com/search",
        headers={
            "User-Agent": get_useragent(),
            "Accept": "*/*"
        },
        params=params,
        proxies=proxies,
        timeout=timeout,
        verify=ssl_verify,
        cookies={
            'CONSENT': 'PENDING+987',  # Bypass the consent page
            'SOCS': 'CAESHAgBEhIaAB',
        }
    )
    resp.raise_for_status()
    return resp


class SearchResult:
    """
    Container for detailed search result information.
    """
    def __init__(self, url, title, description):
        self.url = url
        self.title = title
        self.description = description

    def __repr__(self):
        return f"SearchResult(url={self.url}, title={self.title}, description={self.description})"


def search(term, num_results=10, lang="en", proxy=None, advanced=False,
           sleep_interval=0, timeout=5, safe="active", ssl_verify=None,
           region=None, start_num=0, unique=False, start_date=None, end_date=None):
    """
    Search the Google search engine with an optional date range filter.
    
    Parameters:
        term (str): The search query.
        num_results (int, optional): The number of search results to fetch (default is 10).
        lang (str, optional): Language code (default is "en").
        proxy (str, optional): Proxy URL if needed.
        advanced (bool, optional): If True, yields SearchResult objects; otherwise, yields URL strings.
        sleep_interval (int, optional): Time to sleep between requests.
        timeout (int, optional): Request timeout.
        safe (str, optional): Safe search setting.
        ssl_verify (bool, optional): SSL certificate verification flag.
        region (str, optional): Region code.
        start_num (int, optional): The starting index for search results.
        unique (bool, optional): If True, ensures that only unique links are yielded.
        start_date (str, optional): The start date for filtering results.
        end_date (str, optional): The end date for filtering results.
        
    Yields:
        Either a SearchResult object (if advanced=True) or a URL string.
    """
    # Configure proxy settings if provided.
    proxies = {"https": proxy, "http": proxy} if proxy and (proxy.startswith("https") or proxy.startswith("http")) else None

    # Prepare the date range tbs parameter if custom dates are provided.
    date_range_tbs = get_date_range_tbs(start_date, end_date)

    start = start_num
    fetched_results = 0  # Count of results yielded
    fetched_links = set()  # To ensure uniqueness if requested

    while fetched_results < num_results:
        resp = _req(term, num_results - start, lang, start, proxies, timeout,
                    safe, ssl_verify, region, tbs=date_range_tbs)
        soup = BeautifulSoup(resp.text, "html.parser")
        result_block = soup.find_all("div", class_="ezO2md")
        new_results = 0

        for result in result_block:
            link_tag = result.find("a", href=True)
            title_tag = link_tag.find("span", class_="CVA68e") if link_tag else None
            description_tag = result.find("span", class_="FrIlee")

            # Extract the URL. Sometimes the extra check is necessary.
            if link_tag:
                link = unquote(link_tag["href"].split("&")[0].replace("/url?q=", ""))
            else:
                link = ""

            if link in fetched_links and unique:
                continue

            fetched_links.add(link)
            title = title_tag.text if title_tag else ""
            description = description_tag.text if description_tag else ""
            fetched_results += 1
            new_results += 1

            if advanced:
                yield SearchResult(link, title, description)
            else:
                yield link

            if fetched_results >= num_results:
                break

        if new_results == 0:  # No new results were found on this iteration.
            break

        start += 10  # Prepare for the next page of results.
        sleep(sleep_interval)


