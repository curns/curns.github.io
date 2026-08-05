---
layout: page
title: "places"
permalink: /places.html
---

These are posts connected to a particular place. London is listed separately in its own [category]({{ '/category/london/' | relative_url }}).

{% assign place_names = site.posts | map: "location" | compact | uniq | sort_natural %}
{% for place_name in place_names %}
{% unless place_name == "London" %}
{% assign place_posts = site.posts | where: "location", place_name %}

<h2 id="{{ place_name | slugify }}">{{ place_name }}</h2>
<ul>
{% for post in place_posts %}
<li><a href="{{ post.url | relative_url }}">{{ post.title }}</a> ({{ post.date | date: "%d %b %Y" }})</li>
{% endfor %}
</ul>
{% endunless %}
{% endfor %}
