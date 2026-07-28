---
layout: page
title: "archive"
---

After <span id="online-writing-length">31 and a half years</span> of writing online, I’ve recorded thoughts on radio and advertising, technology and media, theatre, music and books, travel, London and the everyday things that seemed worth noting at the time. Looking back, it’s interesting how many reflect a moment in time. Some posts are still useful, some are snapshots of a web—or even a life—that has moved on, and some make me wonder what I was thinking. A selection of them is here, arranged by category or year. {% assign earliest_post = site.posts | sort: "date" | first %} Or, start at the beginning with [{{ earliest_post.title }}]({{ earliest_post.url | relative_url }}).

<div style="display: flex; justify-content: space-between; gap: 20px;">
  <div style="width: 48%;">
    <h3>Category</h3>
    <ul style="list-style-type: none; padding: 0;">
      {% for category in site.categories %}
        {% assign category_name = category[0] %}
        {% assign category_label = site.data.category_labels[category_name] %}
        {% unless category_label %}
          {% assign category_label = category_name | replace: "-", " " | capitalize %}
        {% endunless %}
        {% assign post_count = category[1] | size %}
        <li style="margin-bottom: 5px;">
          <a href="{{ site.baseurl }}/category/{{ category_name | slugify }}/" style="text-decoration: none; color: #007bff;">
            {{ category_label }} ({{ post_count }})
          </a>
        </li>
      {% endfor %}
    </ul>
  </div>

  <div style="width: 48%;">
    <h3>Year</h3>
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
