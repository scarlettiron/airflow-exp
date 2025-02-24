module.exports = [
  {
    id: 'olym_ext',
    autoStart: true,
    activate: function (app) {
      console.log(
        'JupyterLab extension olym_ext is activated!'
      );

      //const leftSidebar = document.querySelector('.jp-SideBar');
      //document.querySelector('#jp-main-content-panel').removeChild(leftSidebar);
      //console.log(app.commands);
    }
  }
];
