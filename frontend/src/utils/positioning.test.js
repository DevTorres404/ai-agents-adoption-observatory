import { test } from 'node:test';
import assert from 'node:assert/strict';
import { median, positioningData, projectScore, restoreScore } from './positioning.js';

const row = (name, a, p, n = 1) => ({ nombre_agente: name, adopcion: a, popularidad: p, total_observaciones: n });
test('median handles odd, even and empty groups', () => {
  assert.equal(median([1, 8, 3, 2]), 2.5);
  assert.equal(median([7, 1, 3]), 3);
  assert.equal(median([]), 0);
});
test('zeros and fractional scores are not replaced with one', () => {
  const { points } = positioningData([row('Zero', 0, 0), row('Small', .1, .5)]);
  assert.equal(points[1].x, 0);
  assert.equal(points[1].adopcion, 0);
  assert.equal(points[0].adopcion, .1);
  for (const value of [0, .01, 1, 100, 1000000]) {
    assert.ok(Math.abs(restoreScore(projectScore(value, 'log'), 'log') - value) < 1e-7);
  }
});
test('invalid scores excluded rather than fabricated', () => {
  const result = positioningData([row('Null', null, 1), row('NaN', 'invalid', 1), row('Negative', -1, 0), row('Zero', '0', '0')]);
  assert.equal(result.omitted, 3);
  assert.equal(result.points.length, 1);
  assert.ok(result.xAxis.domain[0] < 0 && result.xAxis.domain[1] > 0);
});
test('changing scale preserves identity, quadrants and scores', () => {
  const data = [row('A', 0, 9), row('B', 9, 9), row('C', 9, 0), row('D', 0, 0)];
  const a = positioningData(data, 'log'), b = positioningData(data, 'linear');
  assert.equal(a.medAdop, 4.5);
  assert.equal(a.medPop, 4.5);
  assert.deepEqual(a.points.map(p => [p.nombre_agente, p.marker, p.quadrant.label, p.adopcion]),
    b.points.map(p => [p.nombre_agente, p.marker, p.quadrant.label, p.adopcion]));
  assert.deepEqual(new Set(a.points.map(p => p.quadrant.label)), new Set(['Líderes', 'Retadores', 'Especializados', 'Emergentes']));
});
test('coincident agents remain separate and sizes are bounded', () => {
  const result = positioningData([row('A', 10, 10, 0), row('B', 10, 10, 1000000)]);
  assert.equal(result.points.length, 2);
  assert.notEqual(result.points[0].marker, result.points[1].marker);
  assert.equal(result.points[0].x, result.points[1].x);
  result.points.forEach(p => assert.ok(p.radius >= 9 && p.radius <= 14));
});
test('non-finite volumes do not break marker geometry', () => {
  const result = positioningData([row('Valid', 1, 1, Infinity), row('Blank', ' ', 1), row('Boolean', false, 1)]);
  assert.equal(result.points.length, 1);
  assert.equal(result.points[0].radius, 9);
});
