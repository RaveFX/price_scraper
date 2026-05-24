// Application State Management
const state = {
    products: [],
    stats: null,
    activeTab: 'catalog',
    filters: {
        search: '',
        brand: '',
        model: '',
        shop: '',
        category: 'Android',
        inStockOnly: false,
        sortBy: 'name-asc'
    },
    chartInstance: null
};

// API Endpoint URLs
const API_BASE = '/api';
const ENDPOINTS = {
    stats: `${API_BASE}/stats`,
    products: `${API_BASE}/products`,
    trends: `${API_BASE}/trends`,
    scrape: `${API_BASE}/scrape`,
    scrapeStatus: `${API_BASE}/scrape/status`
};

// DOM Elements
const DOM = {
    navItems: document.querySelectorAll('.nav-item'),
    tabPanes: document.querySelectorAll('.tab-pane'),
    
    // Stats elements
    statProducts: document.getElementById('stat-products'),
    statShops: document.getElementById('stat-shops'),
    statPriceChange: document.getElementById('stat-price-change'),
    statLastUpdate: document.getElementById('stat-last-update'),
    
    // Filter elements
    searchInput: document.getElementById('search-input'),
    brandFilter: document.getElementById('brand-filter'),
    modelFilter: document.getElementById('model-filter'),
    shopFilter: document.getElementById('shop-filter'),
    priceSort: document.getElementById('price-sort'),
    stockToggle: document.getElementById('stock-toggle'),
    
    // Grid loader & container
    gridLoader: document.getElementById('grid-loader'),
    productsGrid: document.getElementById('products-grid'),
    
    // Modals
    trendModal: document.getElementById('trend-modal'),
    trendModalTitle: document.getElementById('trend-modal-title'),
    trendModalSubtitle: document.getElementById('trend-modal-subtitle'),
    btnCloseTrend: document.getElementById('btn-close-trend'),
    
    compareModal: document.getElementById('compare-modal'),
    compareModalTitle: document.getElementById('compare-modal-title'),
    btnCloseCompare: document.getElementById('btn-close-compare'),
    compareTableBody: document.getElementById('compare-table-body'),
    bestShopName: document.getElementById('best-shop-name'),
    bestShopSavings: document.getElementById('best-shop-savings'),
    
    // Scraper panel
    btnTriggerScrape: document.getElementById('btn-trigger-scrape'),
    scraperStatusBadge: document.getElementById('scraper-status-badge'),
    scraperLastRun: document.getElementById('scraper-last-run'),
    btnClearConsole: document.getElementById('btn-clear-console'),
    consoleLogs: document.getElementById('console-logs')
};

// Initial Setup
document.addEventListener('DOMContentLoaded', () => {
    initApp();
    setupEventListeners();
});

// App Initialization
async function initApp() {
    await fetchStats();
    await fetchProducts();
    pollScraperStatus(); // Check initial status of scraper
}

// Event Listeners Routing
function setupEventListeners() {
    // Navigation Tabs
    DOM.navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            switchTab(item);
        });
    });
    
    // Filters & Sorting Input
    DOM.searchInput.addEventListener('input', (e) => {
        state.filters.search = e.target.value.trim().toLowerCase();
        renderProductsGrid();
    });
    
    DOM.brandFilter.addEventListener('change', (e) => {
        state.filters.brand = e.target.value;
        populateModelDropdown();
        renderProductsGrid();
    });
    
    DOM.modelFilter.addEventListener('change', (e) => {
        state.filters.model = e.target.value;
        renderProductsGrid();
    });
    
    DOM.shopFilter.addEventListener('change', (e) => {
        state.filters.shop = e.target.value;
        renderProductsGrid();
    });
    
    DOM.priceSort.addEventListener('change', (e) => {
        state.filters.sortBy = e.target.value;
        renderProductsGrid();
    });
    
    DOM.stockToggle.addEventListener('change', (e) => {
        state.filters.inStockOnly = e.target.checked;
        renderProductsGrid();
    });
    
    // Close Modals
    DOM.btnCloseTrend.addEventListener('click', () => closeModal(DOM.trendModal));
    DOM.btnCloseCompare.addEventListener('click', () => closeModal(DOM.compareModal));
    
    // Close modals on clicking outside panels
    window.addEventListener('click', (e) => {
        if (e.target === DOM.trendModal) closeModal(DOM.trendModal);
        if (e.target === DOM.compareModal) closeModal(DOM.compareModal);
    });
    
    // Scraper Actions
    DOM.btnTriggerScrape.addEventListener('click', triggerScrape);
    DOM.btnClearConsole.addEventListener('click', () => {
        DOM.consoleLogs.textContent = 'Console cleared. Click "Run Daily Scrapers Now" to start a new crawl.';
    });
}

// Switch Navigation Tabs
function switchTab(item) {
    // Remove active from all sidebar items
    DOM.navItems.forEach(el => el.classList.remove('active'));
    item.classList.add('active');
    
    const tabId = item.getAttribute('data-tab');
    const category = item.getAttribute('data-category');
    
    state.filters.category = category || '';
    state.activeTab = tabId;
    
    // Update tab panes
    DOM.tabPanes.forEach(pane => {
        if (pane.id === `tab-${tabId}`) {
            pane.classList.add('active');
        } else {
            pane.classList.remove('active');
        }
    });
    
    if (tabId === 'catalog') {
        state.filters.brand = '';
        state.filters.model = '';
        DOM.brandFilter.value = '';
        DOM.modelFilter.value = '';
        
        populateBrandDropdown();
        populateModelDropdown();
        renderProductsGrid();
    }
}

// Fetch Stats API
async function fetchStats() {
    try {
        const response = await fetch(ENDPOINTS.stats);
        if (!response.ok) throw new Error("Network status was not ok");
        const data = await response.ok ? await response.json() : null;
        if (!data) return;
        
        state.stats = data;
        
        // Populate stats elements
        DOM.statProducts.textContent = data.total_products;
        DOM.statShops.textContent = data.total_shops;
        
        // Style price change rate
        const drift = data.price_change_pct;
        DOM.statPriceChange.textContent = `${drift > 0 ? '+' : ''}${drift}%`;
        if (drift < 0) {
            DOM.statPriceChange.parentNode.previousElementSibling.className = "stat-icon green-accent";
            DOM.statPriceChange.parentNode.previousElementSibling.innerHTML = '<i class="fa-solid fa-trend-down"></i>';
        } else if (drift > 0) {
            DOM.statPriceChange.parentNode.previousElementSibling.className = "stat-icon pink-accent";
            DOM.statPriceChange.parentNode.previousElementSibling.innerHTML = '<i class="fa-solid fa-trend-up"></i>';
        } else {
            DOM.statPriceChange.parentNode.previousElementSibling.className = "stat-icon blue-accent";
            DOM.statPriceChange.parentNode.previousElementSibling.innerHTML = '<i class="fa-solid fa-arrows-left-right"></i>';
        }
        
        DOM.statLastUpdate.textContent = formatDate(data.latest_date);
        
        // Populate Brand drop down filter dynamically based on category
        populateBrandDropdown();
        
        // Populate Shop drop down filter
        const originalShopValue = DOM.shopFilter.value;
        DOM.shopFilter.innerHTML = '<option value="">All Shops</option>';
        data.shops.sort().forEach(shop => {
            const opt = document.createElement('option');
            opt.value = shop;
            opt.textContent = shop;
            DOM.shopFilter.appendChild(opt);
        });
        DOM.shopFilter.value = originalShopValue;
        
    } catch (e) {
        console.error("Error loading stats:", e);
    }
}

// Fetch Products list
async function fetchProducts() {
    DOM.gridLoader.style.display = 'flex';
    DOM.productsGrid.style.display = 'none';
    
    try {
        const response = await fetch(ENDPOINTS.products);
        if (!response.ok) throw new Error("Product load failed");
        
        state.products = await response.json();
        populateBrandDropdown();
        populateModelDropdown();
        renderProductsGrid();
    } catch (e) {
        console.error("Error loading products:", e);
        DOM.productsGrid.innerHTML = `
            <div class="glass-panel" style="grid-column: 1/-1; padding: 40px; text-align: center; color: var(--accent-pink);">
                <i class="fa-solid fa-triangle-exclamation" style="font-size: 2rem; margin-bottom: 12px;"></i>
                <h4>Failed to connect to backend analytics database</h4>
                <p style="color: var(--text-secondary); margin-top: 6px;">Ensure python uvicorn web server is running and master dataset exists.</p>
            </div>
        `;
    } finally {
        DOM.gridLoader.style.display = 'none';
        DOM.productsGrid.style.display = 'grid';
    }
}

// Populate the dynamic Brand selection dropdown list based on category
function populateBrandDropdown() {
    const originalValue = DOM.brandFilter.value;
    DOM.brandFilter.innerHTML = '<option value="">All Brands</option>';
    
    let filteredProducts = state.products;
    if (state.filters.category) {
        filteredProducts = filteredProducts.filter(p => p.category.toLowerCase() === state.filters.category.toLowerCase());
    }
    
    // Get unique brand names
    const brands = Array.from(new Set(filteredProducts.map(p => p.brand))).sort();
    
    brands.forEach(brand => {
        const opt = document.createElement('option');
        opt.value = brand;
        opt.textContent = brand;
        DOM.brandFilter.appendChild(opt);
    });
    
    if (brands.includes(originalValue)) {
        DOM.brandFilter.value = originalValue;
    } else {
        state.filters.brand = '';
        DOM.brandFilter.value = '';
    }
}

// Populate the dynamic Model selection dropdown list
function populateModelDropdown() {
    const originalValue = DOM.modelFilter.value;
    DOM.modelFilter.innerHTML = '<option value="">All Models</option>';
    
    let filteredProducts = state.products;
    if (state.filters.category) {
        filteredProducts = filteredProducts.filter(p => p.category.toLowerCase() === state.filters.category.toLowerCase());
    }
    if (state.filters.brand) {
        filteredProducts = filteredProducts.filter(p => p.brand.toLowerCase() === state.filters.brand.toLowerCase());
    }
    
    // Distinct sorted titles/models
    const models = Array.from(new Set(filteredProducts.map(p => p.title))).sort();
    
    models.forEach(model => {
        const opt = document.createElement('option');
        opt.value = model;
        opt.textContent = model;
        DOM.modelFilter.appendChild(opt);
    });
    
    if (models.includes(originalValue)) {
        DOM.modelFilter.value = originalValue;
        state.filters.model = originalValue;
    } else {
        state.filters.model = '';
        DOM.modelFilter.value = '';
    }
}

// Filter and render the products grid in DOM
function renderProductsGrid() {
    DOM.productsGrid.innerHTML = '';
    
    // Apply filters in client memory
    let filtered = state.products.filter(p => {
        // Search text check
        const matchSearch = p.title.toLowerCase().includes(state.filters.search) || 
                            p.brand.toLowerCase().includes(state.filters.search);
                             
        // Brand selector check
        const matchBrand = !state.filters.brand || p.brand.toLowerCase() === state.filters.brand.toLowerCase();
        
        // Model selector check
        const matchModel = !state.filters.model || p.title === state.filters.model;
        
        // Shop selector check
        const matchShop = !state.filters.shop || p.variants.some(v => v.shop_prices.some(sp => sp.shop === state.filters.shop));
        
        // Category check
        const matchCategory = !state.filters.category || p.category.toLowerCase() === state.filters.category.toLowerCase();
        
        return matchSearch && matchBrand && matchModel && matchShop && matchCategory;
    });
    
    // Render list
    if (filtered.length === 0) {
        DOM.productsGrid.innerHTML = `
            <div class="glass-panel" style="grid-column: 1/-1; padding: 60px 40px; text-align: center; color: var(--text-secondary);">
                <i class="fa-solid fa-magnifying-glass" style="font-size: 2.5rem; color: var(--text-muted); margin-bottom: 16px;"></i>
                <h4>No tracking products match your active filters</h4>
                <p style="color: var(--text-muted); margin-top: 6px;">Try adjusting search text or resetting brand selection.</p>
            </div>
        `;
        return;
    }
    
    // Pre-calculate current price for sorting purposes based on first variant selection
    filtered.forEach(p => {
        if (p.variants && p.variants.length > 0) {
            // Sort variants to find first RAM/Storage
            p._firstVarPrice = getCheapestVariantPrice(p.variants[0]);
            p._firstVarInStock = p.variants.some(v => v.shop_prices.some(sp => sp.in_stock));
        } else {
            p._firstVarPrice = p.min_price;
            p._firstVarInStock = p.in_stock;
        }
    });
    
    // Apply Stock toggle filter
    if (state.filters.inStockOnly) {
        filtered = filtered.filter(p => p._firstVarInStock);
    }
    
    // Apply sorting
    if (state.filters.sortBy === 'name-asc') {
        filtered.sort((a, b) => a.title.localeCompare(b.title));
    } else if (state.filters.sortBy === 'price-asc') {
        filtered.sort((a, b) => a._firstVarPrice - b._firstVarPrice);
    } else if (state.filters.sortBy === 'price-desc') {
        filtered.sort((a, b) => b._firstVarPrice - a._firstVarPrice);
    }
    
    // Render cards
    filtered.forEach(prod => {
        const card = createProductCard(prod);
        DOM.productsGrid.appendChild(card);
    });
}

function getCheapestVariantPrice(variant) {
    const prices = variant.shop_prices.map(sp => sp.price).filter(p => p > 0);
    return prices.length > 0 ? Math.min(...prices) : 0;
}

// Construct dynamic HTML elements for each phone card
function createProductCard(prod) {
    const card = document.createElement('div');
    card.className = 'product-card';
    card.id = `card-${prod.product_id}`;
    
    // Unique ID for dropdown binding
    const dropdownId = `dropdown-${prod.product_id}`;
    
    // 1. Sort variants by RAM, Storage size to list dropdown logically
    const sortedVariants = [...prod.variants].sort((a, b) => {
        const aStorage = parseInt(a.storage) || 0;
        const bStorage = parseInt(b.storage) || 0;
        if (aStorage !== bStorage) return aStorage - bStorage;
        const aRam = parseInt(a.ram) || 0;
        const bRam = parseInt(b.ram) || 0;
        return aRam - bRam;
    });
    
    // Populate variant option elements
    let variantOptions = '';
    sortedVariants.forEach((v, index) => {
        const valueStr = JSON.stringify({ ram: v.ram, storage: v.storage });
        variantOptions += `<option value='${valueStr}' ${index === 0 ? 'selected' : ''}>${v.ram} / ${v.storage}</option>`;
    });
    
    // Render card skeleton
    card.innerHTML = `
        <span class="product-badge" id="badge-${prod.product_id}">--</span>
        <div class="product-brand">${prod.brand}</div>
        <h3 class="product-title" title="${prod.title}">${prod.title}</h3>
        
        <div class="variant-selector-box">
            <label for="${dropdownId}">Memory Configuration</label>
            <select class="variant-dropdown" id="${dropdownId}">
                ${variantOptions}
            </select>
        </div>
        
        <div class="pricing-display">
            <span class="pricing-label">Cheapest LKR Deal:</span>
            <div class="price-value-container">
                <span class="price-amount" id="price-${prod.product_id}">--</span>
                <span class="price-currency" id="currency-${prod.product_id}">LKR</span>
            </div>
        </div>
        
        <div class="shop-indicators-row">
            <span>Sold by:</span>
            <div class="shop-icons-stack" id="shops-${prod.product_id}">
                <!-- Mini badges populated dynamically -->
            </div>
        </div>
        
        <div class="card-buttons">
            <button class="btn btn-secondary" onclick="openTrendModal('${prod.product_id}', '${prod.title}')">
                <i class="fa-solid fa-chart-line"></i> Trends
            </button>
            <button class="btn btn-primary" onclick="openCompareModal('${prod.product_id}', '${prod.title}')">
                <i class="fa-solid fa-shop"></i> Compare
            </button>
        </div>
    `;
    
    // Dropdown change binding to adjust pricing & availability badges dynamically
    const dropdown = card.querySelector(`[id="${dropdownId}"]`);
    dropdown.addEventListener('change', (e) => {
        const val = JSON.parse(e.target.value);
        updateCardVariantDetails(card, prod, val.ram, val.storage);
    });
    
    // Perform initial card binding for the first variant
    if (sortedVariants.length > 0) {
        updateCardVariantDetails(card, prod, sortedVariants[0].ram, sortedVariants[0].storage);
    }
    
    return card;
}

// Update card displays on dropdown selection change
function updateCardVariantDetails(card, prod, ram, storage) {
    const prodId = prod.product_id;
    const badge = card.querySelector(`[id="badge-${prodId}"]`);
    const priceText = card.querySelector(`[id="price-${prodId}"]`);
    const currencyText = card.querySelector(`[id="currency-${prodId}"]`);
    const shopsContainer = card.querySelector(`[id="shops-${prodId}"]`);
    
    // Find selected variant matching specs
    const v = prod.variants.find(item => item.ram === ram && item.storage === storage);
    if (!v) return;
    
    // 1. Calculate stock status (based on selected shop if shop filter is active, otherwise any shop)
    let inStock = false;
    if (state.filters.shop) {
        inStock = v.shop_prices.some(sp => sp.shop === state.filters.shop && sp.in_stock);
    } else {
        inStock = v.shop_prices.some(sp => sp.in_stock);
    }
    
    if (inStock) {
        badge.className = "product-badge instock";
        badge.textContent = "In Stock";
    } else {
        badge.className = "product-badge outofstock";
        badge.textContent = "Out of Stock";
    }
    
    // 2. Find cheapest cash price (filtered by shop if active)
    let validPrices = v.shop_prices.filter(sp => sp.price > 0);
    if (state.filters.shop) {
        validPrices = validPrices.filter(sp => sp.shop === state.filters.shop);
    }
    
    if (validPrices.length > 0) {
        // Sort to get cheapest in-stock first, or just cheapest
        const sortedPrices = [...validPrices].sort((a, b) => {
            if (a.in_stock && !b.in_stock) return -1;
            if (!a.in_stock && b.in_stock) return 1;
            return a.price - b.price;
        });
        const bestDeal = sortedPrices[0];
        
        priceText.textContent = formatNumber(bestDeal.price);
        priceText.classList.remove('preorder');
        currencyText.style.display = 'inline';
        
        // Show cheapest seller text
        let sellerEl = card.querySelector('.cheapest-seller-label');
        if (!sellerEl) {
            sellerEl = document.createElement('div');
            sellerEl.className = 'cheapest-seller-label';
            card.querySelector('.pricing-display').appendChild(sellerEl);
        }
        sellerEl.innerHTML = `at <span class="seller-name">${bestDeal.shop}</span>`;
    } else {
        // Price is 0 or no prices found for selected shop
        priceText.textContent = state.filters.shop ? "NO PRICE" : "PRE-ORDER";
        priceText.classList.add('preorder');
        currencyText.style.display = 'none';
        
        let sellerEl = card.querySelector('.cheapest-seller-label');
        if (sellerEl) sellerEl.remove();
    }
    
    // 3. Render list of shop badges selling this variant
    shopsContainer.innerHTML = '';
    v.shop_prices.forEach(sp => {
        const b = document.createElement('span');
        const shopClass = sp.shop.toLowerCase().replace(' ', '');
        b.className = `shop-mini-badge ${shopClass}`;
        b.textContent = sp.shop;
        b.style.opacity = sp.in_stock ? '1' : '0.4'; // Dim out if shop is out of stock
        b.title = `${sp.shop} (${sp.in_stock ? 'In Stock' : 'Out of Stock'})`;
        
        // Highlight the badge if it matches the selected shop filter
        if (state.filters.shop && sp.shop === state.filters.shop) {
            b.style.borderWidth = '2px';
            b.style.boxShadow = '0 0 8px currentColor';
        }
        
        shopsContainer.appendChild(b);
    });
}

// Modal Toggle utilities
function openModal(modal) {
    modal.classList.add('open');
}

function closeModal(modal) {
    modal.classList.remove('open');
}

// 1. Price Trends Historical Chart Modal Logic
async function openTrendModal(productId, productTitle) {
    const dropdown = document.querySelector(`#dropdown-${productId}`);
    if (!dropdown) return;
    
    const specs = JSON.parse(dropdown.value);
    
    DOM.trendModalTitle.textContent = productTitle;
    DOM.trendModalSubtitle.textContent = `Historic tracking for ${specs.ram} / ${specs.storage} configuration (LKR)`;
    
    openModal(DOM.trendModal);
    
    // Query data
    try {
        const url = `${ENDPOINTS.trends}?product_id=${productId}&ram=${encodeURIComponent(specs.ram)}&storage=${encodeURIComponent(specs.storage)}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error("Trend fetch failed");
        const trends = await response.json();
        
        renderTrendChart(trends);
    } catch (e) {
        console.error("Error drawing trend chart:", e);
        alert("Failed to query price trends. Verify backend connection.");
        closeModal(DOM.trendModal);
    }
}

// Render dynamic lines using Chart.js inside canvas
function renderTrendChart(trends) {
    const ctx = document.getElementById('trend-chart').getContext('2d');
    
    // Destroy existing chart if present to prevent rendering overlaps
    if (state.chartInstance) {
        state.chartInstance.destroy();
    }
    
    // Extract unique sorted dates across all shops for X-axis labels
    const allDates = new Set();
    Object.values(trends).forEach(shopTrends => {
        shopTrends.forEach(t => allDates.add(t.date));
    });
    const sortedLabels = Array.from(allDates).sort();
    
    // Colors catalog for shop lines
    const shopColors = {
        "luxuryx": { stroke: "#ff3366", fillStart: "rgba(255, 51, 102, 0.15)" },
        "simplytek": { stroke: "#00ccff", fillStart: "rgba(0, 204, 255, 0.15)" },
        "gqmobiles": { stroke: "#ff9900", fillStart: "rgba(255, 153, 0, 0.15)" },
        "lifemobile": { stroke: "#00ff88", fillStart: "rgba(0, 255, 136, 0.15)" },
        "smartmobile": { stroke: "#e040fb", fillStart: "rgba(224, 64, 251, 0.15)" }
    };
    
    const datasets = [];
    
    Object.entries(trends).forEach(([shopName, shopData]) => {
        const shopKey = shopName.toLowerCase().replace(' ', '');
        const colors = shopColors[shopKey] || { stroke: "#a0a0a0", fillStart: "rgba(160, 160, 160, 0.05)" };
        
        // Map data to corresponding date indexes
        const dataMap = {};
        shopData.forEach(item => {
            dataMap[item.date] = item.price;
        });
        
        const pricesList = sortedLabels.map(date => {
            const p = dataMap[date];
            return p > 0 ? p : null; // Represent preorders/zeros as nulls to break line segment nicely
        });
        
        // Build dataset configuration
        datasets.push({
            label: shopName,
            data: pricesList,
            borderColor: colors.stroke,
            backgroundColor: colors.fillStart,
            fill: true,
            tension: 0.35, // Smooth spline line curves
            borderWidth: 3,
            pointRadius: 4,
            pointBackgroundColor: colors.stroke,
            pointHoverRadius: 6,
            spanGaps: true
        });
    });
    
    // Draw chart in canvas element
    state.chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: sortedLabels.map(d => formatDate(d)),
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#9ea3b8',
                        font: { family: 'Outfit', size: 12, weight: 600 }
                    }
                },
                tooltip: {
                    padding: 14,
                    bodyFont: { family: 'Outfit', size: 13 },
                    titleFont: { family: 'Outfit', size: 13, weight: 700 },
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) label += ': ';
                            if (context.parsed.y !== null) {
                                label += 'Rs. ' + formatNumber(context.parsed.y);
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                    ticks: { color: '#9ea3b8', font: { family: 'Outfit' } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                    ticks: {
                        color: '#9ea3b8',
                        font: { family: 'Outfit' },
                        callback: function(value) {
                            return 'Rs. ' + formatNumber(value);
                        }
                    }
                }
            }
        }
    });
}

// 2. Shop Pricing Comparative Modal Logic
function openCompareModal(productId, productTitle) {
    const dropdown = document.querySelector(`#dropdown-${productId}`);
    if (!dropdown) return;
    
    const specs = JSON.parse(dropdown.value);
    
    DOM.compareModalTitle.textContent = productTitle;
    
    // Find the product in state
    const prod = state.products.find(p => p.product_id === productId);
    if (!prod) return;
    
    const v = prod.variants.find(item => item.ram === specs.ram && item.storage === specs.storage);
    if (!v) return;
    
    // Sort shops by cheapest price first, placing out of stock or preorders at the bottom
    const sortedShops = [...v.shop_prices].sort((a, b) => {
        // If a price is 0 (pre-order), treat as infinite cost for sorting
        const priceA = a.price > 0 ? a.price : Infinity;
        const priceB = b.price > 0 ? b.price : Infinity;
        
        if (a.in_stock && !b.in_stock) return -1;
        if (!a.in_stock && b.in_stock) return 1;
        return priceA - priceB;
    });
    
    // Render comparative table body
    DOM.compareTableBody.innerHTML = '';
    
    // Identify best price deal
    const inStockDeals = sortedShops.filter(s => s.in_stock && s.price > 0);
    const hasDeals = inStockDeals.length > 0;
    
    let bestDeal = null;
    let worstDeal = null;
    
    if (hasDeals) {
        bestDeal = inStockDeals[0];
        worstDeal = inStockDeals[inStockDeals.length - 1];
        
        DOM.bestShopName.textContent = bestDeal.shop;
        
        // Calculate max potential savings between cheapest and dearest shop
        const savings = worstDeal.price - bestDeal.price;
        if (savings > 0) {
            DOM.bestShopSavings.textContent = `Rs. ${formatNumber(savings)}`;
        } else {
            DOM.bestShopSavings.textContent = "Best Price Match";
        }
    } else {
        DOM.bestShopName.textContent = "No stock available";
        DOM.bestShopSavings.textContent = "--";
    }
    
    sortedShops.forEach((shopDeal, idx) => {
        const tr = document.createElement('tr');
        const isBest = hasDeals && shopDeal.shop === bestDeal.shop && shopDeal.in_stock;
        
        if (isBest) {
            tr.className = "best-row";
        }
        
        const priceDisplay = shopDeal.price > 0 
            ? `Rs. ${formatNumber(shopDeal.price)}` 
            : '<span style="color: var(--accent-green); font-weight: 700;">PRE-ORDER</span>';
            
        tr.innerHTML = `
            <td>
                <span style="font-weight: 600; display: flex; align-items: center; gap: 8px;">
                    ${isBest ? '<i class="fa-solid fa-crown" style="color: gold;" title="Cheapest Shop Deal"></i>' : ''}
                    ${shopDeal.shop}
                </span>
            </td>
            <td>${specs.ram} / ${specs.storage}</td>
            <td>
                <span class="compare-badge ${shopDeal.in_stock ? 'instock' : 'outofstock'}">
                    ${shopDeal.in_stock ? 'In Stock' : 'Out of Stock'}
                </span>
            </td>
            <td><span style="font-family: monospace; font-size: 0.95rem;">${priceDisplay}</span></td>
            <td>
                <a href="${shopDeal.url}" target="_blank" class="buy-link">
                    Go to Shop <i class="fa-solid fa-arrow-up-right-from-square"></i>
                </a>
            </td>
        `;
        
        DOM.compareTableBody.appendChild(tr);
    });
    
    openModal(DOM.compareModal);
}

// 3. Daily Scraper Triggering and Log streaming Logic
async function triggerScrape() {
    DOM.btnTriggerScrape.disabled = true;
    DOM.btnTriggerScrape.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Dispatching Crawler...';
    
    DOM.consoleLogs.textContent = "Connecting to pipeline api and invoking daily crawler script in background...\n";
    switchTab('scraper');
    
    try {
        const response = await fetch(ENDPOINTS.scrape, { method: 'POST' });
        if (!response.ok) throw new Error("Scrape invocation failed");
        
        const resData = await response.json();
        DOM.consoleLogs.textContent += `${resData.message}\nConnecting output stream...\n\n`;
        
        // Start polling status
        setTimeout(pollScraperStatus, 1000);
    } catch (e) {
        console.error("Error triggering scrape:", e);
        DOM.consoleLogs.textContent += `\nError: Failed to trigger scrape pipeline. Ensure uvicorn server is online.`;
        DOM.btnTriggerScrape.disabled = false;
        DOM.btnTriggerScrape.innerHTML = '<i class="fa-solid fa-play"></i> Run Daily Scrapers Now';
    }
}

let pollInterval = null;

function pollScraperStatus() {
    if (pollInterval) clearInterval(pollInterval);
    
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(ENDPOINTS.scrapeStatus);
            if (!response.ok) throw new Error("Status query failed");
            
            const data = await response.json();
            
            // Adjust scraper control badge UI
            DOM.scraperStatusBadge.textContent = data.status;
            DOM.scraperStatusBadge.className = `value badge ${data.status}`;
            
            if (data.last_run) {
                DOM.scraperLastRun.textContent = formatDate(data.last_run.split('T')[0]) + ' ' + data.last_run.split('T')[1].substring(0, 5);
            }
            
            // Output logs stream to console
            if (data.output) {
                DOM.consoleLogs.textContent = data.output;
                // Auto scroll console logs to bottom
                DOM.consoleLogs.scrollTop = DOM.consoleLogs.scrollHeight;
            }
            
            // Check completed states
            if (data.status === 'success' || data.status === 'failed') {
                clearInterval(pollInterval);
                pollInterval = null;
                DOM.btnTriggerScrape.disabled = false;
                DOM.btnTriggerScrape.innerHTML = '<i class="fa-solid fa-play"></i> Run Daily Scrapers Now';
                
                // If it was a success, let's refresh statistics and products list dynamically!
                if (data.status === 'success') {
                    DOM.consoleLogs.textContent += "\n[Pipeline Success] Reloading local Pandas indexes...";
                    await fetchStats();
                    await fetchProducts();
                    DOM.consoleLogs.textContent += " Done ✓";
                }
            }
            
        } catch (e) {
            console.error("Error polling scraper status:", e);
            clearInterval(pollInterval);
            pollInterval = null;
            DOM.btnTriggerScrape.disabled = false;
            DOM.btnTriggerScrape.innerHTML = '<i class="fa-solid fa-play"></i> Run Daily Scrapers Now';
        }
    }, 1500); // Poll status every 1.5 seconds
}

// --- General Formatting Helper Utilities ---
function formatNumber(num) {
    if (!num) return "0";
    return parseInt(num).toLocaleString('en-US');
}

function formatFloat(num) {
    if (!num) return "0.00";
    return parseFloat(num).toFixed(2);
}

function formatDate(dateStr) {
    if (!dateStr) return "--";
    try {
        const parts = dateStr.split('-');
        if (parts.length !== 3) return dateStr;
        
        const date = new Date(parts[0], parts[1] - 1, parts[2]);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch(e) {
        return dateStr;
    }
}
