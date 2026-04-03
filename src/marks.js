function checkResult() {

    let marks = document.getElementById("marks").value;

    if (marks >= 40) {
        document.getElementById("result").innerHTML = "Pass";
    } else {
        document.getElementById("result").innerHTML = "Fail";
    }

}