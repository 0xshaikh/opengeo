"""Real HTML fixtures so unit tests never touch the network."""

WIKI_LIKE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Python explained</title>
<meta name="description" content="Python is a high-level, general-purpose programming language.">
<link rel="canonical" href="https://example.org/python">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Article","headline":"Python explained","author":{"@type":"Person","name":"Ada Lovelace"}}
</script>
</head>
<body>
<h1>Python explained</h1>
<p>Python is a high-level, general-purpose programming language used for automation, data analysis, and web development. It is widely regarded as easy to read because its syntax is plain.</p>
<p>Developers choose Python for many reasons. First, the standard library is large. Second, the ecosystem of packages is enormous. Third, the language is dynamically typed, which makes prototypes quick to write and fast to iterate on. Many teams rely on it daily.</p>
<ul>
<li>Automation and scripting</li>
<li>Data analysis and science</li>
<li>Web frameworks such as Django and FastAPI</li>
<li>Machine learning with scikit-learn and PyTorch</li>
</ul>
<h2>How to learn Python</h2>
<p>Start with a small project. Pick something you actually care about, keep the first version deliberately small, and improve it over time. Most learners find that building a real tool beats reading a textbook end to end, because you meet the errors you will actually meet in production.</p>
<h2>Where Python is used</h2>
<p>Python appears in many organisations for tasks ranging from internal tooling to customer-facing services.</p>
<p>Where do you use Python in your work? Many people answer that they use Python for glue code that ties services together. Others say they use it to prepare data before analysis.</p>
<a href="/docs/intro.html">Introduction</a>
<a href="https://example.org/">Home</a>
<a href="https://example.org/python">Python official site</a>
<a href="https://other-site.example/notes">External notes</a>
<a href="https://blog.example.net/reviews">Blog reviews</a>
</body>
</html>"""

NO_JSONLD = """<!doctype html>
<html>
<head><title>Minimal page</title></head>
<body>
<h1>Minimal page</h1>
<h3>Skipped level</h3>
<p>One short paragraph that stands alone.</p>
</body>
</html>"""

EMPTY_JSONLD = """<!doctype html>
<html><head><title>Broken JSON-LD</title></head>
<body><h1>Borked</h1>
<script type="application/ld+json">{"@type":"Article","headline":"Missing context"}</script>
</body></html>"""
