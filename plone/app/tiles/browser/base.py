# -*- coding: utf-8 -*-
from AccessControl import Unauthorized
from plone.autoform.form import AutoExtensibleForm
from plone.z3cform.interfaces import IDeferSecurityCheck
from z3c.form.interfaces import IWidgets, IDataManager
from zope.component import getMultiAdapter
from zope.security import checkPermission
from zope.traversing.browser.absoluteurl import absoluteURL
from plone.uuid.interfaces import IUUID
from plone.app.uuid.utils import uuidToObject
from z3c.relationfield import RelationValue
from zope.component import getUtility
from zope.intid.interfaces import IIntIds


try:
    from plone.app.drafts.interfaces import ICurrentDraftManagement
    PLONE_APP_DRAFTS = True
except ImportError:
    PLONE_APP_DRAFTS = False


class TileFormLayout(object):
    """Layout view giving access to macro slots
    """

    def __init__(self, context, request):
        self.context = context
        self.request = request

    @property
    def macros(self):
        return self.index.macros


class TileForm(AutoExtensibleForm):
    """Mixin class for tile add/edit forms, which will load the tile schema
    and set up an appropriate form.
    """

    # Must be set by subclass
    tileType = None
    tileId = None

    # Get fieldets if subclass sets additional_schemata
    autoGroups = True

    # We don't want the tile edit screens to use a form prefix, so that we
    # can pass simple things on the edit screen and have them be interpreted
    # by transient tiles
    prefix = ''

    # Name is used to form the form action url
    name = ''

    @property
    def action(self):
        """See interfaces.IInputForm"""
        if self.tileType and self.tileId and self.name:
            tile = self.context.restrictedTraverse(
                '@@%s/%s' % (self.tileType.__name__, self.tileId,))
            url = absoluteURL(tile, self.request)
            url = url.replace('@@', '@@' + self.name.replace('_', '-') + '/')
        else:
            url = self.request.getURL()
        return url

    def update(self):
        # Support drafting tile data context
        if PLONE_APP_DRAFTS:
            ICurrentDraftManagement(self.request).mark()

        # Override to check the tile add/edit permission
        if not IDeferSecurityCheck.providedBy(self.request):
            if not checkPermission(self.tileType.add_permission, self.context):
                raise Unauthorized(
                    "You are not allowed to add this kind of tile")

        super(TileForm, self).update()

    def render(self):
        if self.request.response.getStatus() in (301, 302):
            return ''
        return super(TileForm, self).render()

    def updateWidgets(self):
        # Override to set the widgets prefix before widgets are updated
        self.widgets = getMultiAdapter(
            (self, self.request, self.getContent()), IWidgets)
        self.widgets.prefix = self.tileType.__name__
        self.widgets.mode = self.mode
        self.widgets.ignoreContext = self.ignoreContext
        self.widgets.ignoreRequest = self.ignoreRequest
        self.widgets.ignoreReadonly = self.ignoreReadonly
        self.widgets.update()

    @property
    def description(self):
        return self.tileType.description

    # AutoExtensibleForm contract

    @property
    def schema(self):
        return self.tileType.schema

    def getTileDictForStorage(self, data):
        # Use the appropriate IDataManager for each field to store in
        # the tiles data dict
        all_fields = dict(self.fields)
        for group in self.groups:
            all_fields.update(group.fields)
        storableData = {}
        for k, v in data.items():
            if k in all_fields:
                if isinstance(v, list):  # eg. DataGrid
                    v = map(TileForm.convertToRelations, v)
                dm = getMultiAdapter((storableData, all_fields[k].field), IDataManager)
                dm.set(v)
        return storableData

    def getTileDictFromStorage(self, data):
        all_fields = dict(self.fields)
        for group in self.groups:
            all_fields.update(group.fields)
        d = {}
        for k, v in data.items():
            if k in all_fields:
                dm = getMultiAdapter((data, all_fields[k].field), IDataManager)
                d[k] = dm.get()
                if isinstance(d[k], list):  # eg. DataGrid
                    d[k] = map(TileForm.convertFromRelations, v)
        return d

    @staticmethod
    def convertToRelations(value):
        # see: https://github.com/plone/plone.app.relationfield/blob/master/plone/app/relationfield/widget.py
        # RelationValue objects are constructed using a integer id
        intids = getUtility(IIntIds)
        record = {}
        for record_key, record_value in value.items():
            if (IUUID(record_value, None)):
                to_id = intids.getId(record_value)
                record_value = RelationValue(to_id)
            record[record_key] = record_value
        return record

    @staticmethod
    def convertFromRelations(value):
        record = {}
        for record_key, record_value in value.items():
            if isinstance(record_value, RelationValue):
                try:
                    record[record_key] = record_value.to_object
                except Exception as err:
                    record[record_key] = None  # broken content
            else:
                record[record_key] = record_value
        return record

    additionalSchemata = ()
