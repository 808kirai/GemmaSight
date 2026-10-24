# everyday things read mode knows how to handle, and what to say first for each
# this is guidance for gemma, it does not look anything up
# add a line here to teach gemmasight a new kind of item

everyday_items = [
    ("medicine", "name, strength, dose and how often, then warnings and the expiry date. Read word for word and never guess missing parts"),
    ("money", "currency and value of each note or coin, and the total if there are several. Kenyan shilling notes are 50, 100, 200, 500 and 1000, and the current coins are 1, 5, 10 and 20. Say so if a note is folded or its value is hidden"),
    ("food and drink packaging", "product and brand, then the expiry or best before date, then size or weight. Mention allergens such as nuts, milk, gluten, eggs or soy if they are printed"),
    ("cooking instructions", "steps, times and temperatures in order"),
    ("receipts and bills", "shop or company, the total amount and the date. For bills, also the due date and account or paybill number"),
    ("mobile money and text messages", "who sent it, the amount, the new balance and the transaction code. Read the code letter by letter"),
    ("phone, computer and ATM screens", "the main message, then the buttons or options shown"),
    ("appliance displays and dials", "the numbers on the display and what each knob or dial is set to, for example on a microwave, cooker, iron, kettle or thermostat"),
    ("electricity tokens and meters", "token digits in groups of four, or the meter reading and units"),
    ("clothing labels", "size, material and washing instructions, and the colour of the item"),
    ("cleaning and household products", "product name, what it is for, and safety warnings such as keep away from children or do not mix"),
    ("signs and notices", "the full text, plus any arrows and which way they point"),
    ("vehicles and routes", "route number and destination on buses and matatus, or the registration plate"),
    ("letters, documents and forms", "who it is from and the title, then the main points with any dates or amounts. Summarise long pages"),
    ("books and printed pages", "the heading, then the text in reading order"),
    ("calendars, clocks and watches", "the date or time shown"),
    ("batteries, bulbs and chargers", "type, size, and the voltage or wattage"),
    ("keys, cards and tickets", "what it is and any name, number, seat, date or time printed on it"),
]


def as_prompt_lines():
    return "\n".join(f"- {name}: {what}." for name, what in everyday_items)
