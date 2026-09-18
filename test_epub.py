from ebooklib import epub

book = epub.read_epub("sample.epub")

title_metadata = book.get_metadata("DC", "title")
author_metadata = book.get_metadata("DC", "creator")

title = title_metadata[0][0] if title_metadata else "Unknown Title"
author = author_metadata[0][0] if author_metadata else "Unknown Author"

if author.strip().lower() in ["<unknown>", "unknown", ""]:
    author = "Unknown Author"

print("Title:", title)
print("Author:", author)