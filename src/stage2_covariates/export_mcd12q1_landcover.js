// MCD12Q1 extraction on the exact study-pixel grid.
// Replace YOUR_GEE_PROJECT and asset paths with assets owned by your account.
var assetRoot = 'projects/YOUR_GEE_PROJECT/assets/phenology';
var points20_30 = ee.FeatureCollection(assetRoot + '/stage2b_lc_points_20_30');
var points30_40 = ee.FeatureCollection(assetRoot + '/stage2b_lc_points_30_40');
var points40_50 = ee.FeatureCollection(assetRoot + '/stage2b_lc_points_40_50');
var points50_60 = ee.FeatureCollection(assetRoot + '/stage2b_lc_points_50_60');

var collection = ee.ImageCollection('MODIS/061/MCD12Q1')
  .filterDate('2001-01-01', '2024-01-01')
  .select('LC_Type1');

var mode = collection.mode().rename('igbp_mode');
var validYears = collection.count().rename('valid_years');
var persistence = collection.map(function(image) {
  return image.eq(mode).rename('mode_match');
}).sum().divide(validYears).rename('mode_persistence');
var output = mode.addBands(validYears).addBands(persistence);

function exportPartition(points, label) {
  var sampled = output.sampleRegions({
    collection: points,
    properties: [
      'study_pixel_id', 'pixel_row', 'pixel_col', 'era_cell_id',
      'landscape_type', 'pixel_area_km2', 'latitude', 'longitude'
    ],
    scale: 500,
    geometries: false,
    tileScale: 4
  });
  Export.table.toDrive({
    collection: sampled,
    description: 'stage2b_mcd12q1_' + label,
    folder: 'stage2b_landcover',
    fileNamePrefix: 'stage2b_mcd12q1_' + label,
    fileFormat: 'CSV',
    selectors: [
      'study_pixel_id', 'pixel_row', 'pixel_col', 'era_cell_id',
      'landscape_type', 'pixel_area_km2', 'latitude', 'longitude',
      'igbp_mode', 'valid_years', 'mode_persistence'
    ]
  });
}

exportPartition(points20_30, '20_30');
exportPartition(points30_40, '30_40');
exportPartition(points40_50, '40_50');
exportPartition(points50_60, '50_60');

print('MCD12Q1 years', collection.size());
