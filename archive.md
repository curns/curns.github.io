---
layout: page
title: "archive"
---

<div style="display: flex; justify-content: space-between; gap: 20px;">
  <div style="width: 48%;">
    <h3>Posts by Category</h3>
    <ul style="list-style-type: none; padding: 0;">
      {% for category in site.categories %}
        {% assign category_name = category[0] %}
        {% assign post_count = category[1] | size %}
        <li style="margin-bottom: 5px;">
          <a href="{{ site.baseurl }}/category/{{ category_name | slugify }}/" style="text-decoration: none; color: #007bff;">
            {{ category_name | capitalize }} ({{ post_count }})
          </a>
        </li>
      {% endfor %}
    </ul>
  </div>

  <div style="width: 48%;">
    <h3>Posts by Year</h3>
    <ul style="list-style-type: none; padding: 0;">
      {% assign posts_by_year = site.posts | group_by_exp: "post", "post.date | date: '%Y'" %}
      {% for year in posts_by_year %}
        <li style="margin-bottom: 5px;">
          <a href="{{ site.baseurl }}/year/{{ year.name }}/" style="text-decoration: none; color: #007bff;">
            {{ year.name }} ({{ year.items | size }})
          </a>
        </li>
      {% endfor %}
    </ul>
  </div>
</div>
