from lxml.cssselect import CSSSelector
from zope.testbrowser.browser import Browser
from splinter.element_list import ElementList
from splinter.driver import DriverAPI, ElementAPI
from splinter.cookie_manager import CookieManagerAPI

import mimetypes
import lxml.html
import mechanize

class CookieManager(CookieManagerAPI):

    def __init__(self, browser_cookies):
        self._cookies = browser_cookies

    def add(self, cookies):
        for key, value in cookies.items():
            self._cookies[key] = value

    def delete(self, *cookies):
        if cookies:
            for cookie in cookies:
                try:
                    del self._cookies[cookie]
                except KeyError:
                    pass
        else:
            self._cookies.clearAll()

    def __getitem__(self, item):
        return self._cookies[item]

    def __eq__(self, other_object):
        if isinstance(other_object, dict):
            return dict(self._cookies) == other_object


class ZopeTestBrowser(DriverAPI):

    driver_name = "zope.testbrowser"

    def __init__(self, user_agent=None):
        mech_browser = self._get_mech_browser(user_agent)
        self._browser = Browser(mech_browser=mech_browser)

        self._cookie_manager = CookieManager(self._browser.cookies)
        self._last_urls = []

    def visit(self, url):
        self._browser.open(url)

    def back(self):
        self._last_urls.insert(0, self.url)
        self._browser.goBack()

    def forward(self):
        try:
            self.visit(self._last_urls.pop())
        except IndexError:
            pass

    def reload(self):
        self._browser.reload()

    def quit(self):
        pass

    @property
    def title(self):
        return self._browser.title

    @property
    def html(self):
        return self._browser.contents

    @property
    def url(self):
        return self._browser.url

    def find_option_by_value(self, value):
        html = lxml.html.fromstring(self.html)
        element = html.xpath('//option[@value="%s"]' % value)[0]
        control = self._browser.getControl(element.text)
        return ElementList([ZopeTestBrowserOptionElement(control, self)], find_by="value", query=value)

    def find_option_by_text(self, text):
        html = lxml.html.fromstring(self.html)
        element = html.xpath('//option[normalize-space(text())="%s"]' % text)[0]
        control = self._browser.getControl(element.text)
        return ElementList([ZopeTestBrowserOptionElement(control, self)], find_by="text", query=text)

    def find_by_css(self, selector):
        xpath = CSSSelector(selector).path
        return self.find_by_xpath(xpath, original_find="css", original_selector=selector)

    def find_by_xpath(self, xpath, original_find=None, original_selector=None):
        html = lxml.html.fromstring(self.html)

        elements = []

        for xpath_element in html.xpath(xpath):
            if self._element_is_link(xpath_element):
                return self.find_link_by_text(xpath_element.text)
            elif self._element_is_control(xpath_element):
                return self.find_by_name(xpath_element.name)
            else:
                elements.append(xpath_element)

        find_by = original_find or "xpath"
        query = original_selector or xpath

        return ElementList([ZopeTestBrowserElement(element, self) for element in elements], find_by=find_by, query=query)

    def find_by_tag(self, tag):
        return self.find_by_xpath('//%s' % tag, original_find="tag", original_selector=tag)

    def find_by_value(self, value):
        return self.find_by_xpath('//*[@value="%s"]' % value, original_find="value", original_selector=value)

    def find_by_id(self, id_value):
        return self.find_by_xpath('//*[@id="%s"][1]' % id_value, original_find="id", original_selector=id_value)

    def find_by_name(self, name):
        elements = []
        index = 0

        while True:
            try:
                control = self._browser.getControl(name=name, index=index)
                elements.append(control)
                index += 1
            except IndexError:
                break
        return ElementList([ZopeTestBrowserControlElement(element, self) for element in elements], find_by="name", query=name)

    def find_link_by_text(self, text):
        return self._find_links_by_xpath("//a[text()='%s']" % text)

    def find_link_by_href(self, href):
        return self._find_links_by_xpath("//a[@href='%s']" % href)

    def find_link_by_partial_href(self, partial_href):
        return self._find_links_by_xpath("//a[contains(@href, '%s')]" % partial_href)

    def find_link_by_partial_text(self, partial_text):
        return self._find_links_by_xpath("//a[contains(text(), '%s')]" % partial_text)

    def fill(self, name, value):
        self.find_by_name(name=name).first._control.value = value

    def fill_form(self, field_values):
        for name, value in field_values.items():
            element = self.find_by_name(name)
            control = element.first._control
            if control.type == 'text':
                control.value = value
            elif control.type == 'checkbox':
                if value:
                    control.value = control.options
                else:
                    control.value = []
            elif control.type == 'radio':
                control.value = [option for option in control.options if option == value]
            elif control.type == 'select':
                control.value = [value]

    def choose(self, name, value):
        control = self._browser.getControl(name=name)
        control.value = [option for option in control.options if option == value]

    def check(self, name):
        control = self._browser.getControl(name=name)
        control.value = control.options

    def uncheck(self, name):
        control = self._browser.getControl(name=name)
        control.value = []

    def attach_file(self, name, file_path):
        control = self._browser.getControl(name=name)
        content_type, _ = mimetypes.guess_type(file_path)
        control.add_file(open(file_path), content_type, None)

    def _find_links_by_xpath(self, xpath):
        html = lxml.html.fromstring(self.html)
        links = html.xpath(xpath)
        return ElementList([ZopeTestBrowserLinkElement(link, self) for link in links], find_by="xpath", query=xpath)

    def select(self, name, value):
        self.find_by_name(name).first._control.value = [value]

    def _element_is_link(self, element):
        return element.tag == 'a'

    def _element_is_control(self, element):
        return hasattr(element, 'type')

    def _get_mech_browser(self, user_agent):
        mech_browser = mechanize.Browser()
        if user_agent is not None:
            mech_browser.addheaders = [("User-agent", user_agent),]
        return mech_browser

    @property
    def cookies(self):
        return self._cookie_manager


class ZopeTestBrowserElement(ElementAPI):

    def __init__(self, element, parent):
        self._element = element
        self.parent = parent

    def __getitem__(self, attr):
        return self._element.attrib[attr]

    def find_by_css(self, selector):
        elements = self._element.cssselect(selector)
        return ElementList([self.__class__(element, self) for element in elements])

    def find_by_xpath(self, selector):
        elements = self._element.xpath(selector)
        return ElementList([self.__class__(element, self) for element in elements])

    def find_by_name(self, name):
        elements = self._element.cssselect('[name="%s"]' % name)
        return ElementList([self.__class__(element, self) for element in elements])

    def find_by_tag(self, name):
        elements = self._element.cssselect(name)
        return ElementList([self.__class__(element, self) for element in elements])

    def find_by_value(self, value):
        elements = self._element.cssselect('[value="%s"]' % value)
        return ElementList([self.__class__(element, self) for element in elements])

    def find_by_id(self, id):
        elements = self._element.cssselect('#%s' % id)
        return ElementList([self.__class__(element, self) for element in elements])

    @property
    def value(self):
        return self._element.text

    @property
    def text(self):
        return self.value


class ZopeTestBrowserLinkElement(ZopeTestBrowserElement):

    def __init__(self, element, parent):
        super(ZopeTestBrowserLinkElement, self).__init__(element, parent)
        self._browser = parent._browser

    def __getitem__(self, attr):
        return super(ZopeTestBrowserLinkElement, self).__getitem__(attr)

    def click(self):
        return self._browser.open(self["href"])


class ZopeTestBrowserControlElement(ElementAPI):

    def __init__(self, control, parent):
        self._control = control
        self.parent = parent

    def __getitem__(self, attr):
        return self._control.mech_control.attrs[attr]

    @property
    def value(self):
        return self._control.value

    @property
    def checked(self):
        return bool(self._control.value)

    def click(self):
        return self._control.click()

    def fill(self, value):
        self._control.value = value


class ZopeTestBrowserOptionElement(ElementAPI):

    def __init__(self, control, parent):
        self._control = control
        self.parent = parent

    def __getitem__(self, attr):
        return self._control.mech_item.attrs[attr]

    @property
    def text(self):
        return self._control.mech_item.get_labels()[0]._text

    @property
    def value(self):
        return self._control.optionValue

    @property
    def selected(self):
        return self._control.mech_item._selected

