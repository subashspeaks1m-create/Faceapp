"""Geometry/locality tests with arrays and explicit test adapters, not AI benchmarks."""

import sys
import time
import unittest
from pathlib import Path
import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "apps/inference-engine"))
from inference_pipeline import (  # noqa: E402 — local standalone module path is configured above
    Detection,
    Transform,
    EditedCrop,
    PipelineError,
    canonical_landmarks,
    similarity_matrix,
    align_face,
    seam_blend,
    FilterDispatcher,
    InferencePipeline,
    SkinSmoothing,
)


class Detector:
    def detect(self, image):
        return [Detection(np.array([100, 100, 420, 440]), canonical_landmarks(), 0.99)]


class EmptyDetector:
    def detect(self, image):
        return []


class Parser:
    def parse(self, image):
        return np.ones((512, 512), np.uint8)


class BadModule:
    def apply(self, crop, labels, request, deadline):
        return EditedCrop(crop, np.full((512, 512), np.nan))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.image = np.random.default_rng(8).integers(0, 256, (768, 768, 3), dtype=np.uint8)
        self.crop = self.image[128:640, 128:640].copy()
        self.matrix = np.array([[1, 0, -128], [0, 1, -128]], np.float32)
        self.valid = np.ones((512, 512), np.float32)
        self.mask = np.zeros((512, 512), np.float32)
        self.mask[160:350, 160:350] = 1

    def pipeline(self, detector=None, **kwargs):
        return InferencePipeline(
            detector or Detector(), Parser(), FilterDispatcher({"skin_smooth": SkinSmoothing()}), **kwargs
        )

    def test_similarity_recovers_known_scale_rotation_translation(self):
        a = canonical_landmarks()
        theta = 0.23
        rotation = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
        b = a @ (rotation * 1.3).T + np.array([14, -28])
        m = similarity_matrix(a, b)
        np.testing.assert_allclose(a @ m[:, :2].T + m[:, 2], b, atol=1e-4)
        self.assertGreater(np.linalg.det(m[:, :2]), 0)

    def test_degenerate_alignment_fails(self):
        with self.assertRaises(PipelineError):
            similarity_matrix(np.ones((5, 2)), canonical_landmarks())

    def test_alignment_returns_512_and_source_validity(self):
        crop, m, v = align_face(self.image, Detector().detect(self.image)[0])
        self.assertEqual(crop.shape, (512, 512, 3))
        self.assertEqual(v.shape, (512, 512))
        np.testing.assert_allclose(m, np.array([[1, 0, 0], [0, 1, 0]]), atol=1e-4)

    def test_zero_delta_does_not_resample_source(self):
        out = seam_blend(self.image, self.crop, EditedCrop(self.crop, self.mask), self.matrix, self.valid)
        np.testing.assert_array_equal(out, self.image)

    def test_changed_pixels_stay_in_finite_support(self):
        edit = np.minimum(self.crop.astype(np.int16) + 35, 255).astype(np.uint8)
        out = seam_blend(self.image, self.crop, EditedCrop(edit, self.mask), self.matrix, self.valid)
        self.assertTrue(np.any(out != self.image))
        outside = np.ones((768, 768), bool)
        outside[270:500, 270:500] = False
        np.testing.assert_array_equal(out[outside], self.image[outside])

    def test_untargeted_protection_overrides_edits(self):
        protection = np.zeros((768, 768), np.float32)
        protection[300:470, 300:470] = 1
        edit = np.minimum(self.crop.astype(np.int16) + 50, 255).astype(np.uint8)
        out = seam_blend(
            self.image, self.crop, EditedCrop(edit, self.mask), self.matrix, self.valid, protect_mask=protection
        )
        np.testing.assert_array_equal(out[300:470, 300:470], self.image[300:470, 300:470])

    def test_zero_validity_suppresses_reflected_crop_pixels(self):
        out = seam_blend(
            self.image,
            self.crop,
            EditedCrop(np.zeros_like(self.crop), self.mask),
            self.matrix,
            np.zeros_like(self.valid),
        )
        np.testing.assert_array_equal(out, self.image)

    def test_poisson_restores_outside_region(self):
        edited = self.crop.copy()
        edited[160:350, 160:350] = 100
        out = seam_blend(
            self.image,
            self.crop,
            EditedCrop(edited, self.mask),
            self.matrix,
            self.valid,
            method="poisson",
            feather_px=0,
        )
        outside = np.ones((768, 768), bool)
        outside[288:478, 288:478] = False
        np.testing.assert_array_equal(out[outside], self.image[outside])

    def test_zero_strength_is_exact_original(self):
        result = self.pipeline().run(self.image, Transform("skin_smooth", 0))
        np.testing.assert_array_equal(result.image_bgr, self.image)

    def test_missing_approved_filter_fails_closed(self):
        with self.assertRaises(PipelineError) as error:
            self.pipeline().run(self.image, Transform("age_50s", 0.3))
        self.assertEqual(error.exception.code, "FILTER_UNAVAILABLE")

    def test_missing_face_has_safe_code(self):
        with self.assertRaises(PipelineError) as error:
            self.pipeline(EmptyDetector()).run(self.image, Transform("skin_smooth", 0.3))
        self.assertEqual(error.exception.code, "FACE_NOT_FOUND")

    def test_cancel_before_execution(self):
        with self.assertRaises(PipelineError) as error:
            self.pipeline().run(self.image, Transform("skin_smooth", 0.3), canceled=lambda: True)
        self.assertEqual(error.exception.code, "JOB_CANCELED")

    def test_overdue_stage_fails_and_releases_slot(self):
        pipeline = self.pipeline(inference_budget_s=-1)
        with self.assertRaises(PipelineError) as error:
            pipeline.run(self.image, Transform("skin_smooth", 0.3))
        self.assertEqual(error.exception.code, "DEADLINE_EXCEEDED")
        self.assertFalse(pipeline.lock.locked())

    def test_invalid_mask_is_rejected(self):
        with self.assertRaises(PipelineError) as error:
            FilterDispatcher({"bad": BadModule()}).transform(
                self.crop, np.ones((512, 512)), Transform("bad", 0.5), time.monotonic() + 1
            )
        self.assertEqual(error.exception.code, "MODEL_OUTPUT")

    def test_large_or_nonfinite_input_rejected(self):
        with self.assertRaises(PipelineError):
            self.pipeline(max_pixels=10).run(self.image, Transform("skin_smooth", 0.3))
        with self.assertRaises(PipelineError):
            self.pipeline().run(self.image, Transform("skin_smooth", float("nan")))

    def test_empty_image_rejected(self):
        with self.assertRaises(PipelineError) as error:
            self.pipeline().run(np.empty((0, 0, 3), np.uint8), Transform("skin_smooth", 0.5))
        self.assertEqual(error.exception.code, "IMAGE_INVALID")

    def test_skin_module_protects_eyes_and_lips_after_feathering(self):
        class SensitiveParser:
            def parse(self, crop):
                labels = np.ones((512, 512), np.uint8)
                labels[180:230, 190:310] = 4
                labels[320:350, 210:300] = 12
                return labels

        pipeline = InferencePipeline(
            Detector(), SensitiveParser(), FilterDispatcher({"skin_smooth": SkinSmoothing()}), inference_budget_s=5
        )
        out = pipeline.run(self.image, Transform("skin_smooth", 0.8)).image_bgr
        np.testing.assert_array_equal(out[180:230, 190:310], self.image[180:230, 190:310])
        np.testing.assert_array_equal(out[320:350, 210:300], self.image[320:350, 210:300])


if __name__ == "__main__":
    unittest.main()
