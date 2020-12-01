function sortBy(val) {
    window.location.replace("/result?" + "sort=" + val.value);
}

window.onload = function() {
    var searchTerms = document.getElementById("searchTerms").textContent;
    console.log(searchTerms)
    regStr = searchTerms.replace(/ /g, '|')
	console.log(regStr)

	var match = new RegExp(regStr, "gi");

	var comment = document.getElementsByClassName("card-text");

	for (var i = 0; i < comment.length; i++) {
	    comment[i].innerHTML = comment[i].innerHTML.replace(match, (match) => `<strong><mark style="color:red">${match}</mark></strong>`);
	}
}