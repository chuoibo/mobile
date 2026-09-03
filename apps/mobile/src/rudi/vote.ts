/** Local ballot visibility for the RuDi vote screen.
 *
 * Results stay hidden until the person confirms. That is the audit 03.03
 * defect: showing a tally before a ballot is cast teaches the fixture as a
 * result. This helper is the only place the 21 screens may derive a tally.
 */

export function visibleVoteTallies(
  optionCount: number,
  choice: number | null,
  confirmed: boolean,
): number[] {
  const tallies = Array.from({ length: optionCount }, () => 0);
  if (confirmed && choice !== null && choice >= 0 && choice < optionCount) {
    tallies[choice] += 1;
  }
  return tallies;
}
