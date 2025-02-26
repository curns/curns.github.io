---
layout: page
title: Hi
---

Jon Curnow is a London-based product manager specialising in digital advertising solutions for publishers. He will often write about radio, here are a few examples.

<h1>Radio</h1>
<ul>
  {% assign radio_posts = site.posts | where: "categories", "radio" %}
  {% for post in radio_posts %}
    <li>
      <a href="{{ post.url }}">{{ post.title }}</a>, ({{ post.date | date: "%B %Y" }})
    </li>
  {% endfor %}
</ul>

<h1>Other</h1>
<ul>
  {% assign other_posts = site.posts | sort: 'date' %}
  {% for post in other_posts %}
    {% unless post.categories contains "radio" %}
      <li>
        <a href="{{ post.url }}">{{ post.title }}</a>
      </li>
    {% endunless %}
  {% endfor %}
</ul>

<!-- original code 
<ul>
  {% for post in site.posts %}
    <li>
      <a href="{{ post.url }}">{{ post.title }}</a>, ({{ post.date | date: "%B %Y" }})
    </li>
  {% endfor %}
</ul>
-->
