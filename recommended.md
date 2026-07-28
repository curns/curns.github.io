---
layout: page
title: recommended
---

I’ve been writing online since the late 1990s in all sorts of forms: small sites, blogs and longer pieces that interested me. I enjoy the act of writing, and publishing is an incentive to type. Much of the blog writing now struggles to be relevant, or even informative, as it came from a world where cross-blog linking drove conversations; now many of those other sites have vanished (only some of which have been saved for the future, thanks to the [Wayback Machine](https://web.archive.org/web/20260000000000*/curnow.org) and similar initiatives).

Recently, I’ve been slowly reviewing old material, wherever it lived, trying to find my “best bits”: the end-of-reality-programme showreel. It’s been an interesting exercise, and after <span id="online-writing-length">31 and a half years</span> of writing, I’m gradually curating my favourites. I don’t always agree with my past self, but it’s been fun.

{% assign recommended_posts = site.posts | where_exp: "post", "post.best_rank" | sort: "best_rank" %}
<ul class="recommended-posts">
  {% for post in recommended_posts %}
    <li>
      <a href="{{ post.url | relative_url }}">{{ post.title }}</a> — {{ post.best_description }}
    </li>
  {% endfor %}
</ul>

For the authentic blog experience that’s only just being resurrected from a distant time, you might want to see [musak.org](https://www.musak.org/2001/11/about-musak/).

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
