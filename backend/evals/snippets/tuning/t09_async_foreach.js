async function saveAll(items, db) {
  // expect: bug
  items.forEach(async (item) => {
    await db.save(item);
  });
  return `saved ${items.length} items`;
}

module.exports = { saveAll };
