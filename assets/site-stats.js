---
layout: null
---
{% assign total_word_count = 0 %}
{% for post in site.posts %}
  {% assign post_word_count = post.content | strip_html | number_of_words %}
  {% assign total_word_count = total_word_count | plus: post_word_count %}
{% endfor %}

window.siteStats = Object.freeze({
  postCount: {{ site.posts | size }},
  totalWordCount: {{ total_word_count }}
});
