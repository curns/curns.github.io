---
layout: page
title: "categories"
---

<h2>Categories</h2>
<ul>
  {% for category in site.categories %}
    {% assign category_name = category[0] %}
    {% assign post_count = category[1] | size %}
    <li>
      <a href="{{ site.baseurl }}/category/{{ category_name | slugify }}/">
        {{ category_name | capitalize }} ({{ post_count }})
      </a>
    </li>
  {% endfor %}
</ul>
