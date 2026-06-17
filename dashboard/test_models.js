const fs = require('fs');

// We need a minimal DOM-like environment since methods.js and triangle.js are written for the browser.
// But wait, triangle.js and methods.js are just classes! Let's just eval them.

const triangleCode = fs.readFileSync('./js/triangle.js', 'utf8');
const methodsCode = fs.readFileSync('./js/methods.js', 'utf8');

eval(triangleCode);
eval(methodsCode);

const csvText = fs.readFileSync('./comauto_pos.csv', 'utf8');
const triangle = Triangle.fromCSV(csvText);

console.log('--- TRIANGLE PARSED ---');
const summary = triangle.getSummary();
console.log(`Format: ${summary.format}`);
console.log(`AYs: ${summary.accidentYears} (${summary.oldestAY} - ${summary.latestAY})`);
console.log(`Dev Periods: ${summary.devPeriods} (Max ${summary.maxDevAge}m)`);
console.log(`Total Paid: ${summary.totalPaid}`);

console.log('\n--- TESTING METHODS ---');
const customLDFs = triangle.computeLDFs().map(s => s.volumeWeighted || 1.0);

const methodsToTest = ['CL', 'MCL', 'BF', 'BK', 'CC', 'CO', 'CLK'];

methodsToTest.forEach(code => {
  try {
    const MethodClass = METHODS[code];
    console.log(`\nTesting: ${MethodClass.label}...`);
    
    const params = {};
    if (code === 'BF' || code === 'BK' || code === 'CC') {
      params.aprioriLossRatio = 0.65;
    }
    if (code === 'CLK') {
      params.curveType = 'loglogistic';
      params.growthFunction = 'weibull'; // just examples
    }

    const model = new MethodClass();
    model.fit(triangle, params, customLDFs);
    const results = model.getResults();
    const ibnr = model.getTotalIBNR();
    const ult = model.getTotalUltimate();
    
    console.log(`✓ Success. Total IBNR: ${ibnr.toFixed(0)}, Total Ultimate: ${ult.toFixed(0)}`);
  } catch (e) {
    console.error(`✕ Failed: ${e.message}`);
  }
});
