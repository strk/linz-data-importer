import unittest
import ast
import os
import shutil
import re

from PyQt4.QtTest import QTest
from qgis.PyQt.QtCore import Qt, QSettings
from qgis.utils import plugins
from qgis.core import QgsMapLayerRegistry, QgsApplication
import xml.etree.ElementTree as ET

WAIT=1000
API_KEYS=ast.literal_eval(os.getenv('LDS_PLUGIN_API_KEYS', None))
TEST_CONF={'wms':'Chart NZ 252 Lake Wakatipu',
           'wmts':'Chart NZ 632 Banks Peninsula',
           'wfs':'NZ Railway Centrelines (Topo, 1:250k)'
           }

class CorruptXml(unittest.TestCase):
    """
    Test methods for handling corrupt localstore
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up at TestCase init
        """

        # Get the test executors current key so that 
        # We can revert back to when tests are complete
        cls.testers_keys = QSettings().value('ldsplugin/apikeys')
        cls.lds_plugin = plugins.get('ldsplugin')

    @classmethod
    def tearDownClass(cls):
        """
        Clean up at TestCase teardown
        """

        QSettings().setValue('ldsplugin/apikey', cls.testers_keys)

    def setUp(self):
        """
        Runs before each test
        """

        #Get reference to plugin
        self.lds_plugin = plugins.get('ldsplugin')
        self.dlg=self.lds_plugin.service_dlg

        # Dont run cache update
        self.lds_plugin.update_cache=False

        # Domain to run test against lds (only service with all WxS)
        domain='data.linz.govt.nz'
        self.api_key_instance = self.lds_plugin.api_key_instance
        self.api_key_instance.setApiKeys({domain:API_KEYS[domain]})

        # Test data dir and plugin settigns dir
        self.test_dir=os.path.dirname(os.path.realpath(__file__))
        self.test_data_dir=os.path.join(self.test_dir, 'data')
        self.pl_settings_dir=os.path.join(QgsApplication.qgisSettingsDirPath(), "ldsplugin")

        # Delete all service xml files in plugin settigns dir
        search_str = '|'.join(['_{}.xml'.format(x) for x in ['wms','wfs','wmts']])
        for f in os.listdir(self.pl_settings_dir):
            if re.search(search_str, f):
                os.remove(os.path.join(self.pl_settings_dir, f))

        # Copy in /test/data service xml to save time if they exist. 
        # In most cases they dont as I can not make available with API Key
        # via github. If these are not avilable wms and wfs will be fetch for data portal
        files=['{0}_{1}.xml'.format(domain,x) for x in ['wms','wfs','wmts']]
        for f in files:
            file=os.path.join(self.test_data_dir, f)
            if os.path.exists(file):
                shutil.copy(file, self.pl_settings_dir)

        # Copy in corrupt file for the test
        os.remove(os.path.join(self.pl_settings_dir, 'data.linz.govt.nz_wmts.xml'))
        corr_file_name='data.linz.govt.nz_wmts_corrupt.xml'
        corr_file=os.path.join(self.test_data_dir, corr_file_name) #src
        shutil.copy(corr_file, self.pl_settings_dir)

        # Rename
        new_corr_file = os.path.join(self.pl_settings_dir, corr_file_name)
        name_file_to = os.path.join(self.pl_settings_dir, corr_file_name.replace('_corrupt',''))
        os.rename(new_corr_file, name_file_to)
        QTest.qWait(WAIT)

    def tearDown(self):
        """Runs after each test"""
        QTest.qWait(WAIT)
        self.dlg.uTextFilter.setText('')
        self.dlg.close()
        self.services_loaded=False

    def test_handle_corrupt_xml(self):
        """
        Setup has
        1. placed  corrupt file in the cache

        Test
        1. Test file is corrupt
        1. Runs plug
        2. Test file is not corrupt
        """

        #Test file is corrupt
        cpt_file=os.path.join(self.pl_settings_dir, 'data.linz.govt.nz_wmts.xml')
        is_corrupt=False
        try:
            ET.parse(cpt_file)
        except ET.ParseError:
            is_corrupt=True
        self.assertTrue(is_corrupt)
        # Run Plugin
        self.lds_plugin.actions[0].trigger()
        QTest.qWait(WAIT)
        # ensure all services are are present in the table
        data_types=set([self.lds_plugin.proxy_model.index(row, 3).data() 
                       for row in xrange(self.lds_plugin.proxy_model.rowCount())])
        self.assertEqual(len(data_types),3)
        self.assertEqual([u'WMS', u'WFS', u'WMTS'], list(data_types))

class UserWorkFlows (unittest.TestCase):
    """
    Testr user work flows to import data via the plugin
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up at TestCase init
        """

        # Get the test executors current key so that 
        # We can revert back to when tests are complete
        cls.testers_keys = QSettings().value('ldsplugin/apikeys')

    @classmethod
    def tearDownClass(cls):
        """
        Clean up at TestCase teardown
        """

        # Runs at TestCase teardown.
        QSettings().setValue('ldsplugin/apikey', cls.testers_keys)

    def setUp(self):
        """
        Runs before each test
        """

        self.lds_plugin = plugins.get('ldsplugin')
        self.lds_plugin.update_cache=False
        self.dlg=self.lds_plugin.service_dlg

        domain='data.linz.govt.nz'
        self.api_key_instance = self.lds_plugin.api_key_instance
        self.api_key_instance.setApiKeys({domain:API_KEYS[domain]})

        # Run
        self.lds_plugin.actions[0].trigger()

    def tearDown(self):
        """
        Runs after each test
        """

        QTest.qWait(WAIT) # Just because I want to watch it open a close
        self.dlg.uTextFilter.setText('')
        self.dlg.close()
        QgsMapLayerRegistry.instance().removeAllMapLayers()
        self.services_loaded=False
        item = self.dlg.uListOptions.findItems('ALL', Qt.MatchFixedString)[0]
        self.dlg.uListOptions.itemClicked.emit(item)

    def test_wfs_import(self):
        """
        Test display, filtering, selection and importing of WFS data 
        """

        self.import_service('wfs')

    def test_wms_import(self):
        """
        Test display, filtering, selection and importing of WFS data 
        """

        self.import_service('wms')

    def test_wmts_import(self):
        """
        Test display, filtering, selection and importing of WFS data 
        """

        self.import_service('wmts')

    def import_service(self, service):
        """
        Executes tests for all "test_w<x>s_import" methods
        """

        # Select WxS table view
        item = self.dlg.uListOptions.findItems(service.upper(), Qt.MatchFixedString)[0]
        self.dlg.uListOptions.itemClicked.emit(item)

        # Test the tableview widget is current stackedWidget
        self.assertEqual(self.dlg.qStackedWidget.currentIndex(), 0)

        # Test there is data
        self.assertNotEqual(self.lds_plugin.table_model.rowCount(None), 0)

        # Ensure all records are of the selected type
        data_types=set([self.lds_plugin.proxy_model.index(row, 3).data() 
                       for row in xrange(self.lds_plugin.proxy_model.rowCount())])
        self.assertEqual(len(data_types),1)
        self.assertEqual(service.upper(), list(data_types)[0])

        # Filter
        self.dlg.uTextFilter.setText(TEST_CONF[service].replace('(', '\(').replace(')','\)'))
        QTest.qWait(WAIT)

        # Import the first row
        self.dlg.uDatasetsTableView.selectRow(0)
        self.dlg.uBtnImport.clicked.emit(True)

        # Test the LayerRegistry to ensure the layer has been imported
        names = [layer.name() for layer in QgsMapLayerRegistry.instance().mapLayers().values()]
        self.assertEqual(TEST_CONF[service], names[0])

    def test_all_services(self):
        """
        Test all services are shown in table 
        """

        # Set up 
        item = self.dlg.uListOptions.findItems('ALL', Qt.MatchFixedString)[0]
        self.dlg.uListOptions.itemClicked.emit(item)
        # Tests
        # Test there is data
        self.assertNotEqual(self.lds_plugin.table_model.rowCount(None), 0)
        # ensure all services are are present in the table
        data_types=set([self.lds_plugin.proxy_model.index(row, 3).data() 
                       for row in xrange(self.lds_plugin.proxy_model.rowCount())])
        self.assertEqual(len(data_types),3)
        self.assertEqual([u'WMS', u'WFS', u'WMTS'], list(data_types))

def suite():
    suite = unittest.TestSuite()
    suite.addTests(unittest.makeSuite(ApiKeyTest, 'test'))
    return suite

def run_tests():
    unittest.TextTestRunner(verbosity=3).run(suite())