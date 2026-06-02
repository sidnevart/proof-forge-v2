# JavaScript Closures — Session Notes

## What I understand

A closure is a function that "closes over" its outer scope. Even after the outer function returns, the inner function still has access to the variables defined in the outer scope.

```js
function makeCounter() {
  let count = 0;
  return function() {
    count++;
    return count;
  };
}

const counter = makeCounter();
counter(); // 1
counter(); // 2
```

## Questions I had

- Does closure capture the value or the reference?
  → It captures the reference. If the outer variable changes, the closure sees the new value.

- What happens with `var` in loops?
  → Classic bug: all loop iterations share the same `var i` reference. Use `let` or an IIFE.

## Things I'm not sure about

- When exactly does a closure prevent garbage collection?
- How does this relate to module pattern?

## Code I tried

See `../code/counter.js` and `../code/loop-bug.js`.
