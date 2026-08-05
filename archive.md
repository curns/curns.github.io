---
layout: page
title: "archive"
---

After <span id="online-writing-length">31 and a half years</span> of writing online, I’ve recorded thoughts on radio and advertising, technology and media, theatre, music and books, travel, London and the everyday things that seemed worth noting at the time. Looking back, it’s interesting how many reflect a moment in time. Some posts are still useful, some are snapshots of a web—or even a life—that has moved on, and some make me wonder what I was thinking. A selection of them is here, arranged by category, place or year. {% assign earliest_post = site.posts | sort: "date" | first %} Or, start at the beginning with [{{ earliest_post.title }}]({{ earliest_post.url | relative_url }}).

<div class="archive-columns">
  <div>
    <h3>Category</h3>
    <ul class="archive-list">
      {% assign category_names = "" %}
      {% for category in site.categories %}
        {% assign category_names = category_names | append: category[0] | append: "|" %}
      {% endfor %}
      {% assign sorted_category_names = category_names | split: "|" | sort_natural %}
      {% for category_name in sorted_category_names %}
        {% assign category_label = site.data.category_labels[category_name] %}
        {% unless category_label %}
          {% assign category_label = category_name | replace: "-", " " | capitalize %}
        {% endunless %}
        {% assign post_count = site.categories[category_name] | size %}
        <li style="margin-bottom: 5px;">
          <a href="{{ site.baseurl }}/category/{{ category_name | slugify }}/" style="text-decoration: none; color: #007bff;">
            {{ category_label }} ({{ post_count }})
          </a>
        </li>
      {% endfor %}
    </ul>
  </div>

  <div>
    <h3>Places</h3>
    <ul class="archive-list">
      {% assign place_names = site.posts | map: "location" | compact | uniq | sort_natural %}
      {% for place_name in place_names %}
        {% unless place_name == "London" %}
          {% assign place_posts = site.posts | where: "location", place_name %}
          <li style="margin-bottom: 5px;">
            <a href="{{ '/places.html' | relative_url }}#{{ place_name | slugify }}" style="text-decoration: none; color: #007bff;">
              {{ place_name }} ({{ place_posts | size }})
            </a>
          </li>
        {% endunless %}
      {% endfor %}
    </ul>
  </div>

  <div>
    <h3>Year</h3>
    <ul class="archive-list">
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

<script>
  (() => {
    const writingStartYear = 1995;
    const today = new Date();
    const currentMonthIndex = today.getMonth();
    const completedYears = today.getFullYear() - writingStartYear;
    let writingLength;

    if (currentMonthIndex <= 2) {
      writingLength = `just over ${completedYears} years`;
    } else if (currentMonthIndex <= 5) {
      writingLength = `${completedYears} and a quarter years`;
    } else if (currentMonthIndex <= 8) {
      writingLength = `${completedYears} and a half years`;
    } else if (currentMonthIndex <= 10) {
      writingLength = `${completedYears} and three-quarter years`;
    } else {
      writingLength = `almost ${completedYears + 1} years`;
    }

    document.querySelector("#online-writing-length").textContent = writingLength;
  })();
</script>
