(function() {

    // Set CSS `tranform` property for an element
    function setTransform (el, transform) {
        el.style.transform = transform
        el.style.WebkitTransform = transform
    }

    // Current scroll position
    var current = 0
    // Target scroll position
    var target = 0
    // Ease or speed for moving from `current` to `target`
    var ease = 0.075
    // Utility variables for `requestAnimationFrame`
    var rafId = undefined
    var rafActive = false
    // Container element
    var container = document.querySelector('.grid')
    // Array with `.image` elements
    // Variables for storing dimmensions
    var windowWidth, containerHeight, imageHeight


    // The `fakeScroll` is an element to make the page scrollable
    // Here we are creating it and appending it to the `body`
    var fakeScroll = document.createElement('div')
    fakeScroll.className = 'fake-scroll'
    // document.getElementById('gridWrapper').appendChild(fakeScroll)
    document.body.appendChild(fakeScroll)
    // In the `setupAnimation` function (below) we will set the `height` properly

    // Geeting dimmensions and setting up all for animation
    function setupAnimation () {
        // Updating dimmensions
        windowWidth = window.innerWidth
        containerHeight = container.getBoundingClientRect().height
        // Set `height` for the fake scroll element
        fakeScroll.style.height = containerHeight + 'px'
        // Start the animation, if it is not running already
        startAnimation()
    }

    // Update scroll `target`, and start the animation if it is not running already
    function updateScroll () {
        target = window.scrollY || window.pageYOffset
        startAnimation()
        console.log(target)
    }

    // Start the animation, if it is not running already
    function startAnimation () {
        if (!rafActive) {
            rafActive = true
            rafId = requestAnimationFrame(updateAnimation)
        }
    }

    // Do calculations and apply CSS `transform`s accordingly
    function updateAnimation () {
        // Difference between `target` and `current` scroll position
        var diff = target - current
        // `delta` is the value for adding to the `current` scroll position
        // If `diff < 0.1`, make `delta = 0`, so the animation would not be endless
        var delta = Math.abs(diff) < 0.1 ? 0 : diff * ease

        if (delta) { // If `delta !== 0`
            // Update `current` scroll position
            current += delta
            // Round value for better performance
            current = parseFloat(current.toFixed(2))
            // Call `update` again, using `requestAnimationFrame`
            rafId = requestAnimationFrame(updateAnimation)
        } else { // If `delta === 0`
            // Update `current`, and finish the animation loop
            current = target
            rafActive = false
            cancelAnimationFrame(rafId)
        }

        // Set the CSS `transform` corresponding to the custom scroll effect
        setTransform(container, 'translateY('+ -current +'px)')
    }



    // Listen for `resize` event to recalculate dimmensions
    window.addEventListener('resize', setupAnimation)
    // Listen for `scroll` event to update `target` scroll position
    window.addEventListener('scroll', updateScroll)

    // Initial setup
    setupAnimation()

})()
