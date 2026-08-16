"""Everything that runs offline, by hand, and leaves a file behind.

downloads fetch whole datasets, fetchers ask an endpoint per item, extractors
pull a part out of a dataset that is already on disk, prepared_tables turn a
raw source into the table the builders group over, builders derive features,
compute works out numbers that no source carries, and tools report on what
came out.

Nothing in here is called while a model, a price or a decision is worked out.
Those layers only ever read the files this one wrote.
"""
