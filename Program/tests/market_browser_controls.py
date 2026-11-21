"""Open real disclosure controls before interacting with shared market filters."""


def market_control(page, selector):
    control = page.locator(selector)
    # XPath returns enclosing disclosures in document order, outermost first.
    # Use the visible summary just as a user would, including nested year/source
    # details. Do not force clicks or mutate the DOM's open state.
    for disclosure in control.locator("xpath=ancestor::details[not(@open)]").all():
        disclosure.locator(":scope > summary").click()
    return control
