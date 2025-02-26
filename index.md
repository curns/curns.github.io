---
layout: page
title: Hi
---

Jon Curnow is a London-based product manager specialising in digital advertising solutions for publishers. He will often write about radio, here are a few examples.

<ul>
  {% for post in site.posts %}
    <li>
      <a href="{{ post.url }}">{{ post.title }}</a>, ({{ post.date | date: "%B %Y" }})
    </li>
  {% endfor %}
</ul>
