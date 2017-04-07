from collections import OrderedDict
import uuid

from odooku.data.serialization.model import ModelSerializer
from odooku.data.pk import hash_pk


pk_links = {}


class SerializationContext(object):

    def __init__(self, env, strict=False, link=False, config=None):
        self.env = env
        self.strict = strict
        self.link = link
        self._config = config
        self._serializers = None

    @property
    def serializers(self):
        if self._serializers is None:
            self._serializers = OrderedDict([
                (model_name, ModelSerializer.factory(
                    model_name,
                    self.env[model_name], # use iterkeys instead of env iteritems for Odoo 9 compatibiltiy,
                    config=self._config.models.get(model_name, None)
                ))
                for model_name in self.env.registry.iterkeys()
                if not any([
                    # use getattr for Odoo 9 compatibility
                    getattr(self.env[model_name], attr, False)
                    for attr in ['_transient', '_abstract']
                ])
            ])

        return self._serializers

    def _clone(self, cls=None):
        cls = cls or type(self)
        clone = cls(self.env, strict=self.strict, link=self.link, config=self._config)
        clone._serializers = self.serializers
        return clone

    def resolve_dependencies(self, model_name):
        clone = self._clone(DependencyContext)
        return clone

    def new_entry(self, model_name, pk=None):
        clone = self._clone(EntryContext)
        clone.model_name = model_name
        clone.pk = pk
        return clone

    def new_record(self, model_name, pk):
        clone = self._clone(RecordContext)
        clone.model_name = model_name
        clone.pk = pk
        return clone

    def resolve_pk(self, model_name, pk):
        if model_name in pk_links:
            return pk_links[model_name].get(hash_pk(pk), None)

    def link_pk(self, model_name, pk, new_pk=None):
        if model_name not in pk_links:
            pk_links[model_name] = {}

        new_pk = new_pk or pk_links[model_name].get(hash_pk(pk), None)
        if new_pk is None:
            new_pk = str(uuid.uuid4())

        pk_links[model_name][hash_pk(pk)] = new_pk
        return new_pk

class DependencyContext(SerializationContext):

    def __enter__(self):
        self.stack = list()
        return self

    def __exit__(self, type, value, traceback):
        del self.stack


class RecordContext(SerializationContext):

    def __enter__(self):
        self.dependencies = set()
        self.delayed_fields = set()
        return self

    def __exit__(self, type, value, traceback):
        del self.dependencies
        del self.delayed_fields

    def delay_field(self, field_name):
        self.delayed_fields.add(field_name)

    def add_relation(self, relation, pk):
        if relation == self.model_name:
            self.dependencies.add(pk)


class EntryContext(SerializationContext):

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass
