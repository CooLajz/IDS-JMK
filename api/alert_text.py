"""Convert provider markup into readable text and a small attribute-free HTML subset."""

import re
from html import escape, unescape
from html.parser import HTMLParser

TAGS = {
    "b": "strong",
    "strong": "strong",
    "i": "em",
    "em": "em",
    "u": "u",
    "p": "p",
    "div": "p",
    "h1": "p",
    "h2": "p",
    "h3": "p",
    "h4": "p",
    "h5": "p",
    "h6": "p",
    "ul": "ul",
    "ol": "ol",
    "li": "li",
}
BLOCKS = {"p", "ul", "ol", "li"}
HIDDEN = {"script", "style", "iframe", "object", "template", "svg", "math"}


class AlertText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.html = []
        self.stack = []
        self.hidden = []

    def boundary(self):
        self.text.append("\n\n")

    def close_tag(self, tag):
        if tag not in self.stack:
            return
        while self.stack:
            opened = self.stack.pop()
            self.html.append(f"</{opened}>")
            if opened == tag:
                break

    def handle_starttag(self, tag, attrs):
        if tag in HIDDEN:
            self.hidden.append(tag)
        if self.hidden:
            return
        if tag == "br":
            self.text.append("\n")
            self.html.append("<br>")
            return
        mapped = TAGS.get(tag)
        if not mapped:
            return
        if mapped in BLOCKS:
            self.boundary()
            # Provider paragraphs are often unclosed, or begin inside bold text.
            if mapped == "p":
                self.close_tag("p")
                while self.stack and self.stack[-1] not in BLOCKS:
                    self.close_tag(self.stack[-1])
        if mapped == "li":
            list_start = max((i for i, tag in enumerate(self.stack) if tag in {"ul", "ol"}), default=-1)
            if "li" in self.stack[list_start + 1 :]:
                self.close_tag("li")
            self.text.append("• ")
        self.html.append(f"<{mapped}>")
        self.stack.append(mapped)

    def handle_endtag(self, tag):
        if self.hidden:
            if tag in self.hidden:
                self.hidden = self.hidden[: self.hidden.index(tag)]
            return
        mapped = TAGS.get(tag)
        if mapped:
            self.close_tag(mapped)
            if mapped in BLOCKS:
                self.boundary()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag != "br":
            self.handle_endtag(tag)

    def handle_data(self, data):
        if self.hidden:
            return
        data = data.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
        data = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", data)
        self.text.append(data)
        self.html.append(escape(data, quote=False).replace("\n", "<br>"))

    def result(self):
        while self.stack:
            self.close_tag(self.stack[-1])
        text = re.sub(r"[^\S\n]+", " ", "".join(self.text))
        text = "\n".join(line.strip() for line in text.split("\n"))
        return re.sub(r"\n{3,}", "\n\n", text).strip(), "".join(self.html).strip()


def format_alert_text(value):
    # Decode encoded markup too, but never recursively expand arbitrary input.
    for _ in range(2):
        decoded = unescape(value)
        if decoded == value or not re.search(
            r"</?[a-z]|&(?:amp;)?(?:lt;|#0*60;|#x0*3c;)", decoded, re.IGNORECASE
        ):
            break
        value = decoded
    parser = AlertText()
    parser.feed(value)
    parser.close()
    return parser.result()
