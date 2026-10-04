function cheapest(prices) {
  // expect: bug
  const sorted = prices.sort();
  return sorted[0];
}

module.exports = { cheapest };
