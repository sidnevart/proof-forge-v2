function makeCounter(initial = 0) {
  let count = initial;

  return {
    increment() { return ++count; },
    decrement() { return --count; },
    value() { return count; },
    reset() { count = initial; },
  };
}

// Usage
const c = makeCounter(10);
console.log(c.increment()); // 11
console.log(c.increment()); // 12
console.log(c.decrement()); // 11
console.log(c.value());     // 11
c.reset();
console.log(c.value());     // 10
