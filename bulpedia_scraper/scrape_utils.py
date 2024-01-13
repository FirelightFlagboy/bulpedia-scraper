import requests
from lxml import etree
from requests import Session


def debug_html(root: etree._Element) -> None:
    print(etree.tostring(root, pretty_print=True, method="html").decode())


def parse_url_html(url: str, session: Session) -> etree._Element:
    page = send_request(url, session)
    parser = etree.HTMLParser()

    try:
        root = etree.fromstring(page.content, parser)
    except etree.LxmlError as e:
        raise ParseError() from e
    else:
        return root


def send_request(url: str, session: Session) -> requests.Response:
    page = session.get(url)
    if page.status_code != 200:
        raise HTTPError(page.status_code, page.reason)
    return page


class HTTPError(Exception):
    status_code: int
    message: str

    def __init__(self, code: int, message: str, *args: object) -> None:
        self.status_code = code
        self.message = message

        super().__init__(*args)


class ParseError(Exception):
    pass
