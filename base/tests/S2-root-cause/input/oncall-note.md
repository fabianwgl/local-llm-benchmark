Handover from the previous on-call (Thursday 11 Sep, 10:35 UTC):

Since Tuesday's deploy (v2025.09.09-2) the order page throws intermittent 500s. Stack trace and a
log excerpt from this morning are attached. It comes and goes: reloading the page a minute later
usually works.

Tuesday's deploy contained two changes:

1. `render: show the loyalty tier badge next to the customer name` (touches `renderOrder.ts`)
2. `orders: fail fast on slow lookups, timeout 3000ms -> 800ms` (touches `orderService.ts`)

My guess is that some customers have no loyalty tier yet and change 1 blows up on them. I have a
revert of change 1 ready. Can you confirm that is the cause before I ship the revert?
