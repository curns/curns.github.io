---
layout: page
title: london
permalink: /london/
---

I’ve been in London for <span id="london-residency-length">32 and a half years</span>, most of my life, and definitely longer than I have lived anywhere else. I don’t know if [Samuel Johnson was correct](https://www.samueljohnson.com/tiredlon.html), but I am not yet bored of London; there is always something new to discover.

I love the city and think it rewards curiosity and an open mind. Naturally, London became an integral part of my writing, but here I’ve tried to select pieces that capture the heart and soul of the place: the good and the sad. Generally, it’s a place that will put a smile on your face, whether you’re a visitor, a resident or a true sound-of-the-bells Cockney.

{% assign london_posts = site.categories.London | where_exp: "post", "post.london_rank" | sort: "london_rank" %}
<ul class="recommended-posts">
  {% for post in london_posts %}
    <li>
      <a href="{{ post.url | relative_url }}">{{ post.title }}</a> — {{ post.london_description }}
    </li>
  {% endfor %}
</ul>

<script>
  (() => {
    const residencyStartYear = 1993;
    const today = new Date();
    const currentMonthIndex = today.getMonth();
    const completedYears =
      today.getFullYear() - residencyStartYear - (currentMonthIndex < 10 ? 1 : 0);
    let residencyLength;

    if (currentMonthIndex >= 10 || currentMonthIndex === 0) {
      residencyLength = `just over ${completedYears} years`;
    } else if (currentMonthIndex <= 3) {
      residencyLength = `${completedYears} and a quarter years`;
    } else if (currentMonthIndex <= 6) {
      residencyLength = `${completedYears} and a half years`;
    } else if (currentMonthIndex <= 8) {
      residencyLength = `${completedYears} and three-quarter years`;
    } else {
      residencyLength = `almost ${completedYears + 1} years`;
    }

    document.querySelector("#london-residency-length").textContent = residencyLength;
  })();
</script>
