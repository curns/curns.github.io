---
layout: page
title: hi
---

Jon Curnow lives in London and works as a product manager in video advertising. Since 1999, he’s published words on the web; he’s written about all sorts of things — ideas, interests, projects and whatever else caught his attention — across several corners of the web. This site brings some of that writing together in one place. There are currently {{ site.posts | size }} posts collected here; below is a selection.

<h1>Selected Posts</h1>
<ul>
  {% assign ranked_posts = site.posts | sort: "best_rank" %}
  {% for post in ranked_posts %}
    {% if post.star %}
      {% unless post.categories contains "radio" %}
        <li>
          <a href="{{ post.url | relative_url }}">{{ post.title }}</a>, <span style="font-size: 14px; color: #828282;">({{ post.date | date: "%B %Y" }})</span>
        </li>
      {% endunless %}
    {% endif %}
  {% endfor %}
</ul>

There are some [recommendations](/recommended.html), or you can just browse the [archive](/archive.html).

[Radio](/category/radio/) was the first mass medium to capture his imagination. He has a particular affection for local radio: at its best, it gives a place a voice, creates a sense of community and makes a mass audience feel like a conversation between two people.

<h1>Radio</h1>
<ul>
  {% for post in ranked_posts %}
    {% if post.star and post.categories contains "radio" %}
      <li>
        <a href="{{ post.url | relative_url }}">{{ post.title }}</a>, <span style="font-size: 14px; color: #828282;">({{ post.date | date: "%B %Y" }})</span>
      </li>
    {% endif %}
  {% endfor %}
</ul>
