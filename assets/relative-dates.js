(function () {
  "use strict";

  var millisecondsPerDay = 24 * 60 * 60 * 1000;

  function dateParts(dateValue) {
    var match = dateValue.match(/^(\d{4})-(\d{2})-(\d{2})/);

    if (!match) {
      return null;
    }

    return {
      year: Number(match[1]),
      month: Number(match[2]),
      day: Number(match[3])
    };
  }

  function relativeAge(dateValue, now) {
    var published = dateParts(dateValue);

    if (!published) {
      return null;
    }

    var today = {
      year: now.getFullYear(),
      month: now.getMonth() + 1,
      day: now.getDate()
    };
    var publishedTime = Date.UTC(published.year, published.month - 1, published.day);
    var todayTime = Date.UTC(today.year, today.month - 1, today.day);
    var differenceInDays = Math.round((todayTime - publishedTime) / millisecondsPerDay);
    var earlier = differenceInDays >= 0 ? published : today;
    var later = differenceInDays >= 0 ? today : published;
    var absoluteDays = Math.abs(differenceInDays);
    var years = later.year - earlier.year;
    var amount;
    var unit;

    if (later.month < earlier.month ||
        (later.month === earlier.month && later.day < earlier.day)) {
      years -= 1;
    }

    if (years >= 1) {
      amount = years;
      unit = "year";
    } else if (absoluteDays >= 30) {
      amount = (later.year - earlier.year) * 12 + later.month - earlier.month;

      if (later.day < earlier.day) {
        amount -= 1;
      }

      amount = Math.max(1, amount);
      unit = "month";
    } else {
      amount = absoluteDays;
      unit = "day";
    }

    var label = amount + " " + unit + (amount === 1 ? "" : "s");
    return differenceInDays >= 0 ? label + " ago" : "in " + label;
  }

  function addRelativeDates() {
    var now = new Date();
    var dates = document.querySelectorAll(".relative-date[data-date]");

    dates.forEach(function (element) {
      var label = relativeAge(element.getAttribute("data-date"), now);

      if (label) {
        element.textContent = ", " + label;
      }
    });
  }

  addRelativeDates();
}());
