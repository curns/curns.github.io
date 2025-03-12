---
layout: page
title: hi
---

Jon Curnow is a London-based product manager specialising in digital advertising solutions for broadcasters. Across the web he's written about many things. Here' a sample of writing.

<h1>Selected Posts</h1>
<ul>
  {% for post in site.posts %}
    {% if post.star %}
      <li>
        <a href="{{ post.url }}">{{ post.title }}</a> ({{ post.date | date: "%d %b %Y" }})
      </li>
    {% endif %}
  {% endfor %}
</ul>

He used to write a lot about radio, the first mass medium to really interest him.

<h1>Radio</h1>
<ul>
  {% assign radio_posts = site.posts | where: "categories", "radio" | sort: 'date' %}
  {% for post in radio_posts %}
    <li>
      <a href="{{ post.url }}">{{ post.title }}</a>, <span style="font-size: 14px; color: #828282;">({{ post.date | date: "%B %Y" }})</span>
    </li>
  {% endfor %}
</ul>

<!-- Other posts 

<h1>Other</h1>
<ul>
  {% assign other_posts = site.posts | sort: 'date' %}
  {% for post in other_posts %}
    {% unless post.categories contains "radio" %}
      <li>
        <a href="{{ post.url }}">{{ post.title }}</a>, <span style="font-size: 14px; color: #828282;">({{ post.date | date: "%B %Y" }})</span>
      </li>
    {% endunless %}
  {% endfor %}
</ul>

-->

<!-- original code 
<ul>
  {% for post in site.posts %}
    <li>
      <a href="{{ post.url }}">{{ post.title }}</a>, ({{ post.date | date: "%B %Y" }})
    </li>
  {% endfor %}
</ul>
-->
