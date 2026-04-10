---
layout: page
title: contents
permalink: /contents/
robots: noindex, nofollow, noarchive
sitemap: false
---

<p>This page lists equivalent versions of these posts on GitHub Pages, musak.org, and curnow.org where they exist. GitHub has {{ site.data.contents_links.total_word_count }} words currently published.</p>

<p>Blank cells mean no verified equivalent page has been confirmed yet.</p>

<style>
.contents-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.95rem;
}

.contents-table th,
.contents-table td {
  border: 1px solid #d5d7da;
  padding: 0.6rem 0.75rem;
  text-align: left;
  vertical-align: top;
}

.contents-table th {
  background: #f7f7f7;
}

.contents-title {
  font-weight: 600;
}

.contents-meta {
  color: #666;
  font-size: 0.85rem;
  margin-top: 0.2rem;
}
</style>

<table class="contents-table">
  <thead>
    <tr>
      <th>GitHub Pages</th>
      <th>musak.org</th>
      <th>curnow.org</th>
    </tr>
  </thead>
  <tbody>
    {% for entry in site.data.contents_links.entries %}
      <tr>
        <td>
          <div class="contents-title"><a href="{{ entry.github_url }}">{{ entry.title }}</a></div>
          {% if entry.date_display %}
            <div class="contents-meta">
              {{ entry.date_display }}
              {% if entry.word_count %}
                • {{ entry.word_count }} words
              {% endif %}
            </div>
          {% endif %}
        </td>
        <td>
          {% if entry.musak_url %}
            <a href="{{ entry.musak_url }}">musak.org</a>
          {% endif %}
        </td>
        <td>
          {% if entry.curnow_url %}
            <a href="{{ entry.curnow_url }}">curnow.org</a>
          {% endif %}
        </td>
      </tr>
    {% endfor %}
  </tbody>
</table>
