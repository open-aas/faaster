from typing import Any

from faaster.interfaces import IAddressSpace, INode
from faaster.aas_metamodel.models.asset_administration_shell import AssetAdministrationShell as AASModel
from .base import BaseCreator
from faaster.log import get_logger


logger = get_logger(__name__)


class AASCreator(BaseCreator):

    async def create(
            self,
            parent: INode,
            element: AASModel,
            address_space: IAddressSpace,
    ) -> INode:
        name = element.id_short or "AAS"
        node = await address_space.add_object(parent, name)

        # --- propriedades básicas ---
        await address_space.add_property(node, "Id", element.id)
        await address_space.add_property(node, "IdShort", name)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "Category", element.category)

        # --- administration ---
        if element.administration:
            await self.add_administrative_information(
                node, element.administration, address_space
            )

        # --- assetInformation ---
        if element.asset_information:
            await self._create_asset_information(
                node, element.asset_information, address_space
            )

        # --- description ---
        if element.description:
            await self.add_descriptions(
                node, element.description, address_space
            )

        # --- displayName ---
        if element.display_name:
            await self._create_display_name(
                node, element.display_name, address_space
            )

        # --- derivedFrom ---
        if element.derived_from:
            await self._create_derived_from(
                node, element.derived_from, address_space
            )

        # --- submodels ---
        if element.submodels:
            await self._create_submodel_references(
                node, element.submodels, address_space
            )

        # --- embeddedDataSpecifications ---
        if element.embedded_data_specifications:
            await self._create_embedded_data_specifications(
                node, element.embedded_data_specifications, address_space
            )

        # --- extensions ---
        if element.extensions:
            await self._create_extensions(
                node, element.extensions, address_space
            )

        return node

    # -------------------------------------------------------------------------
    # AssetInformation
    # -------------------------------------------------------------------------

    @staticmethod
    async def _create_asset_information(
            parent: INode,
            asset_info: Any,
            address_space: IAddressSpace,
    ) -> INode:
        node = await address_space.add_object(parent, "AssetInformation")

        if asset_info.asset_kind:
            await address_space.add_property(node, "AssetKind", asset_info.asset_kind)
        if asset_info.global_asset_id:
            await address_space.add_property(node, "GlobalAssetId", asset_info.global_asset_id)
        if asset_info.asset_type:
            await address_space.add_property(node, "AssetType", asset_info.asset_type)

        if asset_info.default_thumbnail:
            thumbnail_node = await address_space.add_object(node, "DefaultThumbnail")
            if asset_info.default_thumbnail.path:
                await address_space.add_property(
                    thumbnail_node, "Path", asset_info.default_thumbnail.path
                )

        return node

    # -------------------------------------------------------------------------
    # DisplayName
    # -------------------------------------------------------------------------

    @staticmethod
    async def _create_display_name(
            parent: INode,
            display_names: list,
            address_space: IAddressSpace,
    ) -> None:
        display_name_folder = await address_space.add_folder(parent, "DisplayName")
        for display_name in display_names:
            lang = display_name.language or "und"
            text = display_name.text or ""
            await address_space.add_property(display_name_folder, lang, text)

    # -------------------------------------------------------------------------
    # DerivedFrom
    # -------------------------------------------------------------------------

    @staticmethod
    async def _create_derived_from(
            parent: INode,
            derived_from: Any,
            address_space: IAddressSpace,
    ) -> None:
        derived_node = await address_space.add_folder(parent, "DerivedFrom")

        await address_space.add_property(
            derived_node, "Type", derived_from.type or ""
        )

        if derived_from.keys:
            keys_folder = await address_space.add_folder(derived_node, "Keys")
            for key in derived_from.keys:
                await address_space.add_property(
                    keys_folder,
                    key.type or "Key",
                    key.value or "",
                )

    # -------------------------------------------------------------------------
    # Submodel References
    # -------------------------------------------------------------------------

    @staticmethod
    async def _create_submodel_references(
            parent: INode,
            submodels: list,
            address_space: IAddressSpace,
    ) -> None:
        submodels_folder = await address_space.add_folder(parent, "Submodels")

        for i, ref in enumerate(submodels):
            ref_node = await address_space.add_folder(
                submodels_folder, f"{ref.type.value}[{i}]"
            )
            await address_space.add_property(ref_node, "Type", ref.type or "")

            if ref.keys:
                keys_folder = await address_space.add_folder(ref_node, "Keys")
                for key in ref.keys:
                    await address_space.add_property(
                        keys_folder,
                        key.type or "Key",
                        key.value or "",
                    )

    # -------------------------------------------------------------------------
    # EmbeddedDataSpecifications
    # -------------------------------------------------------------------------

    @staticmethod
    async def _create_embedded_data_specifications(
            parent: INode,
            specs: list,
            address_space: IAddressSpace,
    ) -> None:
        specs_folder = await address_space.add_folder(
            parent, "EmbeddedDataSpecifications"
        )

        for i, spec in enumerate(specs):
            spec_node = await address_space.add_folder(
                specs_folder, f"DataSpecification[{i}]"
            )

            if spec.data_specification:
                ds_node = await address_space.add_folder(
                    spec_node, "DataSpecification"
                )
                await address_space.add_property(
                    ds_node, "Type", spec.data_specification.type or ""
                )
                if spec.data_specification.keys:
                    keys_folder = await address_space.add_folder(ds_node, "Keys")
                    for key in spec.data_specification.keys:
                        await address_space.add_property(
                            keys_folder,
                            key.type or "Key",
                            key.value or "",
                        )

            if spec.data_specification_content:
                content = spec.data_specification_content
                content_node = await address_space.add_folder(
                    spec_node, "DataSpecificationContent"
                )
                await address_space.add_property(
                    content_node, "ModelType", content.type_model or ""
                )
                await address_space.add_property(
                    content_node, "Value", str(content.value or "")
                )

                if content.preferred_name:
                    pn_folder = await address_space.add_folder(
                        content_node, "PreferredName"
                    )
                    # for pn in content.preferred_name:
                    #     lang = pn.language or "und"
                    #     text = pn.text or ""
                    #     await address_space.add_property(pn_folder, lang, text)

    # -------------------------------------------------------------------------
    # Extensions
    # -------------------------------------------------------------------------

    @staticmethod
    async def _create_extensions(
            parent: INode,
            extensions: list,
            address_space: IAddressSpace,
    ) -> None:
        extensions_folder = await address_space.add_folder(parent, "Extensions")

        for ext in extensions:
            ext_node = await address_space.add_folder(
                extensions_folder, ext.name or "Extension"
            )

            await address_space.add_property(ext_node, "Name", ext.name or "")

            if ext.refers_to:
                refers_folder = await address_space.add_folder(ext_node, "RefersTo")
                for i, ref in enumerate(ext.refers_to):
                    ref_node = await address_space.add_folder(
                        refers_folder, f"Reference[{i}]"
                    )
                    await address_space.add_property(
                        ref_node, "Type", ref.type or ""
                    )
                    if ref.keys:
                        keys_folder = await address_space.add_folder(ref_node, "Keys")
                        for key in ref.keys:
                            await address_space.add_property(
                                keys_folder,
                                key.type or "Key",
                                key.value or "",
                            )
