from django.contrib.sitemaps import Sitemap
from .models import Monitoring
from .views import MonitoringDetailView
from django.core.urlresolvers import reverse


class MonitoringSitemap(Sitemap):
    def items(self):
        return Monitoring.objects.all()

    def lastmod(self, obj):
        return obj.modified


class MonitoringPagesSitemap(Sitemap):
    paginate_by = MonitoringDetailView.paginate_by

    def ceildiv(self, a, b):
        return -(-a // b)

    def items(self):
        items = []
        for obj in Monitoring.objects.with_case_count().all():
            for page in xrange(0, self.ceildiv(obj.case_count, self.paginate_by)):
                items.append((obj, page + 1))
        return items

    def location(self, item):
        obj, page = item
        return reverse('monitorings:details', kwargs={'slug': obj.slug,
                                                      'page': page})